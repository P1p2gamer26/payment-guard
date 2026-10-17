import copy
import dataclasses
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import models

from .data import DATA, load_policy
from .domain import Extraction, Policy
from .engine import Decision, Ledger, decide, find_beneficiary
from .explain import explain
from . import arena
from .models import Approval, ArenaRun, DecisionRecord, Event, ExtractionCorrection, Invoice, PolicyVersion, UsedNonce
from .receipt import sign
from .extractor import extract, is_suspicious
from .second_read import read_total

CENT = Decimal("0.01")

# Campos que una persona puede corregir: la cuenta y el beneficiario NUNCA (salen del registro maestro).
CAMPOS_CORRIGIBLES = ("amount", "currency", "issue_date", "invoice_number", "concept")
ISO3 = re.compile(r"^[A-Za-z]{3}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def save_policy(raw: dict) -> PolicyVersion:
    last = PolicyVersion.objects.order_by("-version").values_list("version", flat=True).first()
    return PolicyVersion.objects.create(version=(last or 0) + 1, raw=raw)


def current_policy() -> PolicyVersion:
    pv = PolicyVersion.objects.order_by("-version").first()
    if pv is None:
        pv = save_policy(load_policy().raw)
    return pv


def load_invoices() -> list[Invoice]:
    out = []
    for f in sorted((DATA / "facturas").iterdir()):
        text = f.read_text(encoding="utf-8")
        inv, _ = Invoice.objects.get_or_create(
            invoice_id=f.stem, defaults={"filename": f.name, "text": text}
        )
        out.append(inv)
    return out


def _serialize_extraction(x: Extraction) -> dict:
    d = dataclasses.asdict(x)
    d["amount"] = str(d["amount"])
    d["issue_date"] = d["issue_date"].isoformat() if d["issue_date"] else None
    return d


def _serialize_second_read(sr) -> list | None:
    if sr is None:
        return None
    return [str(sr[0]), sr[1]]


def emit(kind: str, **campos) -> "Event":
    """Registra un evento de auditoría; ignora errores para no romper el flujo principal."""
    try:
        return Event.objects.create(kind=kind, **campos)
    except Exception:
        pass


def process_next(pv: PolicyVersion) -> "DecisionRecord | None":
    """Decide la SIGUIENTE factura sin DecisionRecord en pv; retorna None si ya están todas."""
    policy = Policy(pv.raw, pv.version)
    # facturas ya decididas en esta política
    done_ids = set(
        DecisionRecord.objects.filter(policy_version=pv)
        .values_list("invoice__invoice_id", flat=True)
    )
    # próxima factura en orden
    all_invoices = load_invoices()
    inv = next((i for i in all_invoices if i.invoice_id not in done_ids), None)
    if inv is None:
        return None

    # reconstruir ledger con los PAGAR ya guardados en pv
    pagados = (
        DecisionRecord.objects.filter(policy_version=pv, outcome="PAGAR")
        .order_by("invoice__invoice_id")
        .select_related("invoice")
    )
    paid_xs = [Extraction.from_dict(r.invoice.extraction) for r in pagados if r.invoice.extraction]
    gastado = sum((r.amount_usd for r in pagados if r.amount_usd is not None), Decimal("0"))
    # escaladas pendientes cuentan para anti-fraccionamiento, igual que en process_all
    seen = [Extraction.from_dict(r.invoice.extraction) for r in DecisionRecord.objects.filter(
        policy_version=pv, outcome="ESCALAR").select_related("invoice") if r.invoice.extraction]
    ledger = Ledger(policy.period_budget_remaining_usd - gastado, paid_xs, seen)

    x = extract(inv.text, mode=settings.DECISION_MODE)
    b = find_beneficiary(x, policy)
    x = dataclasses.replace(x, invoice_id=inv.invoice_id, beneficiary_id=b and b["id"],
                            suspicious=x.suspicious or is_suspicious(inv.text, policy.normalizar_unicode))
    sr = read_total(inv.text)
    d = decide(x, policy, ledger, second_read=sr)

    inv.extraction = _serialize_extraction(x)
    inv.save(update_fields=["extraction"])
    rec, _ = DecisionRecord.objects.update_or_create(
        invoice=inv,
        policy_version=pv,
        defaults={
            "outcome": d.outcome,
            "rule": d.rule,
            "amount_usd": d.amount_usd,
            "facts": d.facts,
            "explanation": explain(d, x),
            "second_read": _serialize_second_read(sr),
        },
    )
    rec.receipt = sign(rec)
    rec.save(update_fields=["receipt"])
    emit("decision", invoice_id=inv.invoice_id, outcome=d.outcome, rule=d.rule,
         amount_usd=d.amount_usd, policy_version=pv.version)
    return rec


def process_all(pv: PolicyVersion) -> list[DecisionRecord]:
    policy = Policy(pv.raw, pv.version)
    ledger = Ledger(policy.period_budget_remaining_usd, [])
    records = []
    for inv in load_invoices():
        x = extract(inv.text, mode=settings.DECISION_MODE)
        b = find_beneficiary(x, policy)
        x = dataclasses.replace(x, invoice_id=inv.invoice_id, beneficiary_id=b and b["id"],
                                suspicious=x.suspicious or is_suspicious(inv.text, policy.normalizar_unicode))
        sr = read_total(inv.text)
        d = decide(x, policy, ledger, second_read=sr)
        if d.outcome == "PAGAR":
            ledger.remaining_usd -= d.amount_usd
            ledger.paid.append(x)
        elif d.outcome == "ESCALAR":
            ledger.seen.append(x)
        inv.extraction = _serialize_extraction(x)
        inv.save(update_fields=["extraction"])
        rec, _ = DecisionRecord.objects.update_or_create(
            invoice=inv,
            policy_version=pv,
            defaults={
                "outcome": d.outcome,
                "rule": d.rule,
                "amount_usd": d.amount_usd,
                "facts": d.facts,
                "explanation": explain(d, x),
                "second_read": _serialize_second_read(sr),
            },
        )
        rec.receipt = sign(rec)
        rec.save(update_fields=["receipt"])
        records.append(rec)
        emit("decision", invoice_id=inv.invoice_id, outcome=d.outcome, rule=d.rule,
             amount_usd=d.amount_usd, policy_version=pv.version)
    records.sort(key=lambda r: r.invoice.invoice_id)
    return records


def spent_usd(pv: PolicyVersion) -> Decimal:
    pagados = DecisionRecord.objects.filter(policy_version=pv, outcome="PAGAR")
    gastado = sum((r.amount_usd for r in pagados if r.amount_usd is not None), Decimal("0"))
    aprobados = Approval.objects.filter(outcome="APROBADO", decision__policy_version=pv)
    gastado += sum(
        (a.decision.amount_usd for a in aprobados if a.decision.amount_usd is not None),
        Decimal("0"),
    )
    return gastado


def process_text(text: str, invoice_id: str) -> Decision:
    pv = current_policy()
    policy = Policy(pv.raw, pv.version)
    # lo ya pagado/aprobado alimenta la detección de duplicados, no solo el presupuesto
    done = DecisionRecord.objects.filter(policy_version=pv).filter(
        models.Q(outcome="PAGAR") | models.Q(approval__outcome="APROBADO")).select_related("invoice")
    paid = [Extraction.from_dict(r.invoice.extraction) for r in done if r.invoice.extraction]
    pend = DecisionRecord.objects.filter(policy_version=pv, outcome="ESCALAR", approval__isnull=True).select_related("invoice")
    seen = [Extraction.from_dict(r.invoice.extraction) for r in pend if r.invoice.extraction]
    ledger = Ledger(policy.period_budget_remaining_usd - spent_usd(pv), paid, seen)
    x = extract(text, mode=settings.DECISION_MODE)
    b = find_beneficiary(x, policy)
    x = dataclasses.replace(x, invoice_id=invoice_id, beneficiary_id=b and b["id"],
                            suspicious=x.suspicious or is_suspicious(text, policy.normalizar_unicode))
    return decide(x, policy, ledger, second_read=read_total(text))


def _validar_valor(field: str, value: str) -> str:
    """Normaliza y valida el valor corregido; ValueError con mensaje visible en la UI."""
    v = (value or "").strip()
    if field == "amount":
        try:
            monto = Decimal(v)
        except InvalidOperation:
            raise ValueError(f"monto: «{v}» no es un número.")
        if monto <= 0:
            raise ValueError("monto: debe ser mayor a 0.")
        return str(monto)
    if field == "currency":
        if not ISO3.match(v):
            raise ValueError(f"moneda: «{v}» debe ser un código ISO de 3 letras.")
        return v.upper()
    if field == "issue_date":
        if not ISO_DATE.match(v):
            raise ValueError(f"fecha: «{v}» debe tener formato YYYY-MM-DD.")
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"fecha: «{v}» no es una fecha válida.")
        return v
    if not v:
        raise ValueError(f"{field}: el valor es obligatorio.")
    return v


def _segunda_lectura(rec: DecisionRecord, field: str):
    """El regex de contraste; si la persona corrigió monto/moneda, esa lectura quedó obsoleta."""
    # ponytail: no re-alimentar el regex con un valor que el humano acaba de sobreescribir
    if field in ("amount", "currency") or not rec.second_read:
        return None
    try:
        return (Decimal(str(rec.second_read[0])), str(rec.second_read[1]))
    except (InvalidOperation, IndexError, TypeError):
        return None


def _ledger_previo(pv: PolicyVersion, excluida: Invoice) -> Ledger:
    """Ledger de la política con lo ya pagado/aprobado por personas, sin incluir la factura en curso."""
    policy = Policy(pv.raw, pv.version)
    otros = (
        DecisionRecord.objects.filter(policy_version=pv)
        .exclude(invoice=excluida)
        .filter(models.Q(outcome="PAGAR") | models.Q(approval__outcome="APROBADO"))
        .order_by("invoice__invoice_id")
        .select_related("invoice")
    )
    pagadas = [Extraction.from_dict(r.invoice.extraction) for r in otros if r.invoice.extraction]
    gastado = sum((r.amount_usd for r in otros if r.amount_usd is not None), Decimal("0"))
    return Ledger(policy.period_budget_remaining_usd - gastado, pagadas)


def correct_field(invoice_id: str, field: str, value: str, actor: str, reason: str) -> DecisionRecord:
    """Corrección humana de un campo extraído + re-decisión con la política actual y recibo nuevo."""
    if field not in CAMPOS_CORRIGIBLES:
        raise ValueError(
            f"campo «{field}» no es corregible; use uno de: {', '.join(CAMPOS_CORRIGIBLES)}. "
            "La cuenta y el beneficiario salen del registro maestro, nunca de la factura."
        )
    if not (reason or "").strip():
        raise ValueError("el motivo de la corrección es obligatorio.")
    if not (actor or "").strip():
        raise ValueError("el actor de la corrección es obligatorio.")
    nuevo = _validar_valor(field, (value or "").strip())
    try:
        inv = Invoice.objects.get(invoice_id=invoice_id)
    except Invoice.DoesNotExist:
        raise ValueError(f"factura {invoice_id} no encontrada.")
    pv = current_policy()
    rec = (
        DecisionRecord.objects.filter(invoice=inv, policy_version=pv)
        .select_related("policy_version")
        .first()
    )
    if rec is None:
        raise ValueError("la factura no tiene decisión registrada; reprocese antes de corregir.")
    if Approval.objects.filter(decision=rec).exists():
        raise ValueError("ya fue decidida por una persona")

    ex = dict(inv.extraction or {})
    viejo = "" if ex.get(field) is None else str(ex.get(field))
    ex[field] = nuevo
    ExtractionCorrection.objects.create(
        invoice=inv, field=field, old_value=viejo, new_value=nuevo,
        actor=(actor or "").strip(), reason=(reason or "").strip(),
    )
    inv.extraction = ex
    inv.save(update_fields=["extraction"])

    policy = Policy(pv.raw, pv.version)
    x = Extraction.from_dict(ex)
    d = decide(x, policy, _ledger_previo(pv, inv), second_read=_segunda_lectura(rec, field))
    rec.outcome = d.outcome
    rec.rule = d.rule
    rec.amount_usd = d.amount_usd
    rec.facts = d.facts
    rec.explanation = explain(d, x)
    rec.save()
    # el recibo anterior queda inválido: se quema su nonce y cambian contenido y nonce del nuevo
    if rec.receipt and rec.receipt.get("nonce"):
        UsedNonce.objects.get_or_create(nonce=rec.receipt["nonce"])
    rec.receipt = sign(rec)
    rec.save(update_fields=["receipt"])
    emit("correccion", invoice_id=invoice_id, outcome=rec.outcome, rule=rec.rule,
         amount_usd=rec.amount_usd, message=f"{field}: «{viejo}» → «{nuevo}»",
         policy_version=pv.version)
    return rec


def ensure_receipts(pv: PolicyVersion) -> None:
    for rec in DecisionRecord.objects.filter(policy_version=pv):
        if not rec.receipt:
            try:
                rec.receipt = sign(rec)
                rec.save(update_fields=["receipt"])
            except Exception:
                pass


def mandato_v2(raw: dict) -> dict:
    """Mandato v2: activa las defensas que cierran los huecos que encuentra la arena."""
    raw = copy.deepcopy(raw)
    raw["reglas_pago"]["anti_fraccionamiento"] = True
    raw["reglas_pago"]["normalizar_unicode"] = True
    return raw


def apply_mandato_v2() -> PolicyVersion:
    nueva = save_policy(mandato_v2(current_policy().raw))
    process_all(nueva)
    return nueva


def run_arena(pv: PolicyVersion) -> ArenaRun:
    r = arena.run(Policy(pv.raw, pv.version))
    run = ArenaRun.objects.create(policy_version=pv, total=r.total, indebidos=r.indebidos,
                                  por_categoria=r.por_categoria, ejemplos=r.ejemplos)
    emit("arena", policy_version=pv.version,
         message=f"Arena: {r.indebidos} indebidos de {r.total} (v{pv.version})")
    return run
