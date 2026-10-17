"""Motor de reglas: el código decide, el LLM solo extrae. Default deny."""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .domain import Extraction, Policy

CENT = Decimal("0.01")


@dataclass
class Decision:
    invoice_id: str
    outcome: str  # PAGAR | FRENAR | ESCALAR
    rule: str
    amount_usd: Decimal | None
    facts: dict = field(default_factory=dict)


@dataclass
class Ledger:
    remaining_usd: Decimal
    paid: list[Extraction]


class Hit(Exception):
    def __init__(self, outcome, rule, **facts):
        self.outcome, self.rule, self.facts = outcome, rule, {k: str(v) for k, v in facts.items()}


def _norm(s: str | None) -> str:
    return " ".join((s or "").casefold().split())


def to_usd(x: Extraction, p: Policy) -> Decimal:
    return (x.amount * p.fx[x.currency]).quantize(CENT, ROUND_HALF_UP)


def find_beneficiary(x: Extraction, p: Policy) -> dict | None:
    if x.beneficiary_id in p.beneficiaries:
        return p.beneficiaries[x.beneficiary_id]
    # ponytail: nombre exacto normalizado; fuzzy matching abriría la puerta a suplantación
    return next((b for b in p.beneficiaries.values() if _norm(b["nombre"]) == _norm(x.beneficiary_name)), None)


def _same_beneficiary(a: Extraction, b: Extraction, p: Policy) -> bool:
    ba, bb = find_beneficiary(a, p), find_beneficiary(b, p)
    return ba is not None and ba is bb


# Cada regla recibe un contexto y lanza Hit si dispara. El orden importa: la primera gana.
def r_sospecha(c):
    if c.x.suspicious:
        raise Hit("ESCALAR", "R_SOSPECHA")


def r_confianza(c):
    if c.x.confidence < 0.8:
        raise Hit("ESCALAR", "R_CONFIANZA", confianza=c.x.confidence)


def r_doble_lectura(c):
    if c.second_read and (c.second_read[0] != c.x.amount or c.second_read[1] != c.x.currency):
        raise Hit("ESCALAR", "R_DOBLE_LECTURA", lectura_llm=f"{c.x.currency} {c.x.amount}",
                  lectura_regex=f"{c.second_read[1]} {c.second_read[0]}")


def r_moneda(c):
    if c.x.currency not in c.p.allowed_currencies:
        raise Hit("FRENAR", "R_MONEDA", moneda=c.x.currency, permitidas=", ".join(sorted(c.p.allowed_currencies)))


def r_beneficiario(c):
    if c.ben is None:
        raise Hit("ESCALAR", "R_BENEFICIARIO", nombre=c.x.beneficiary_name)


def r_cuenta(c):
    if _norm(c.x.bank_account) != _norm(c.ben["cuenta"]):
        raise Hit("ESCALAR", "R_CUENTA", cuenta_factura=c.x.bank_account, cuenta_registrada=c.ben["cuenta"])


def r_duplicado(c):
    for y in c.ledger.paid:
        if not _same_beneficiary(c.x, y, c.p):
            continue
        if (c.x.invoice_number and c.x.invoice_number == y.invoice_number) \
                or (_norm(c.x.concept) and _norm(c.x.concept) == _norm(y.concept)) \
                or (c.x.amount == y.amount and c.x.issue_date == y.issue_date):
            raise Hit("FRENAR", "R_DUPLICADO", factura_previa=y.invoice_id, numero_previo=y.invoice_number)


def r_fecha(c):
    age = (c.p.today - c.x.issue_date).days
    if age < 0 or age > c.p.max_age_days:
        raise Hit("FRENAR", "R_FECHA", fecha=c.x.issue_date, hoy=c.p.today, max_dias=c.p.max_age_days)


def r_contrato(c):
    k = c.ben.get("contrato")
    if k and k["moneda"] == c.x.currency:
        monto_k = Decimal(str(k["monto"]))
        if abs(c.x.amount - monto_k) / monto_k * 100 > c.p.contract_tolerance_pct:
            raise Hit("ESCALAR", "R_CONTRATO", monto=c.x.amount, contrato=monto_k, moneda=c.x.currency)


def r_limite(c):
    if c.usd > c.p.per_payment_limit_usd:
        raise Hit("FRENAR", "R_LIMITE", monto_usd=c.usd, limite=c.p.per_payment_limit_usd)


def r_umbral(c):
    if c.usd > c.p.approval_threshold_usd:
        raise Hit("ESCALAR", "R_UMBRAL", monto_usd=c.usd, umbral=c.p.approval_threshold_usd)


def r_presupuesto(c):
    if c.usd > c.ledger.remaining_usd:
        raise Hit("FRENAR", "R_PRESUPUESTO", monto_usd=c.usd, restante=c.ledger.remaining_usd)


RULES = [r_sospecha, r_confianza, r_doble_lectura, r_moneda, r_beneficiario, r_cuenta,
         r_duplicado, r_fecha, r_contrato, r_limite, r_umbral, r_presupuesto]


@dataclass
class _Ctx:
    x: Extraction
    p: Policy
    ledger: Ledger
    second_read: tuple[Decimal, str] | None
    ben: dict | None = None
    usd: Decimal | None = None


def decide(x: Extraction, p: Policy, ledger: Ledger, second_read=None) -> Decision:
    usd = None
    try:
        usd = to_usd(x, p) if x.currency in p.fx else None
        c = _Ctx(x, p, ledger, second_read, find_beneficiary(x, p), usd)
        for rule in RULES:
            rule(c)
        return Decision(x.invoice_id, "PAGAR", "OK", usd, {"monto_usd": str(usd)})
    except Hit as h:
        return Decision(x.invoice_id, h.outcome, h.rule, usd, h.facts)
    except Exception as e:  # default deny: cualquier fallo escala, nunca paga
        return Decision(x.invoice_id, "ESCALAR", "R_ERROR", usd, {"error": type(e).__name__})


def run_batch(xs: list[Extraction], p: Policy) -> list[Decision]:
    ledger = Ledger(p.period_budget_remaining_usd, [])
    out = []
    for x in sorted(xs, key=lambda g: g.invoice_id):
        d = decide(x, p, ledger)
        if d.outcome == "PAGAR":
            ledger.remaining_usd -= d.amount_usd
            ledger.paid.append(x)
        out.append(d)
    return out


def allowed_to_pay(x: Extraction, p: Policy, ledger: Ledger) -> bool:
    """Oráculo independiente: re-chequea los límites duros sin usar RULES ni decide()."""
    r = p.raw["reglas_pago"]
    if x.suspicious or x.confidence < 0.8 or x.currency not in r["monedas_permitidas"]:
        return False
    regs = [b for b in p.raw["beneficiarios_permitidos"]
            if b["id"] == x.beneficiary_id or b["nombre"].casefold().strip() == x.beneficiary_name.casefold().strip()]
    if len(regs) != 1 or regs[0]["cuenta"].strip() != x.bank_account.strip():
        return False
    usd = x.amount * Decimal(str(r["tipos_cambio_a_usd"][x.currency]))
    if usd > Decimal(str(r["limite_por_pago_usd"])) or usd > Decimal(str(r["umbral_aprobacion_humana_usd"])):
        return False
    if usd > ledger.remaining_usd + CENT:
        return False
    if not (0 <= (p.today - x.issue_date).days <= int(r["fecha"]["antiguedad_maxima_dias"])):
        return False
    return all(y.invoice_number != x.invoice_number for y in ledger.paid if y.beneficiary_id == x.beneficiary_id)
