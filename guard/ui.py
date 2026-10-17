"""Modelos de vista para la UI v2: evidencia por campo, ruta de reglas, gauge y datos de la escena 3D.

Solo presentación: ninguna decisión se toma aquí (decide el motor en engine.py).
"""
import re
from decimal import Decimal

from .domain import Policy

# (nombre, descripción, resultado). El orden replica engine.RULES; "OK" cierra la ruta.
REGLAS = [
    ("R_SOSPECHA", "Instrucciones ocultas en el texto (prompt injection)", "ESCALAR"),
    ("R_CONFIANZA", "Falta monto, moneda o cuenta, monto ≤ 0 o lectura poco confiable", "ESCALAR"),
    ("R_UNICODE", "Caracteres invisibles o homoglifos en nombre, cuenta o número (mandato v2)", "ESCALAR"),
    ("R_DOBLE_LECTURA", "El regex lee monto o moneda distintos al LLM", "ESCALAR"),
    ("R_MONEDA", "Moneda fuera de las permitidas", "FRENAR"),
    ("R_BENEFICIARIO", "Beneficiario fuera del registro maestro o ambiguo", "ESCALAR"),
    ("R_CUENTA", "Cuenta distinta de la registrada", "ESCALAR"),
    ("R_DUPLICADO", "Mismo número, concepto o monto+mes que un pago previo", "FRENAR"),
    ("R_FECHA", "Emisión futura o más antigua que la antigüedad máxima", "FRENAR"),
    ("R_CONTRATO", "Monto difiere del contrato más de la tolerancia", "ESCALAR"),
    ("R_LIMITE", "Supera el límite duro por pago", "FRENAR"),
    ("R_FRACCIONAMIENTO", "Pagos del mismo beneficiario en el mes que sumados superan el tope (mandato v2)", "ESCALAR"),
    ("R_UMBRAL", "Supera el umbral de aprobación humana", "ESCALAR"),
    ("R_PRESUPUESTO", "No alcanza el presupuesto restante", "FRENAR"),
    ("OK", "Ninguna regla dispara", "PAGAR"),
]
BASE13 = ["R_SOSPECHA", "R_CONFIANZA", "R_DOBLE_LECTURA", "R_MONEDA", "R_BENEFICIARIO", "R_CUENTA", "R_DUPLICADO",
          "R_FECHA", "R_CONTRATO", "R_LIMITE", "R_UMBRAL", "R_PRESUPUESTO", "OK"]
# anillo (1..13) de la escena 3D para reglas que el túnel base no dibuja
ANILLO_EXTRA = {"R_UNICODE": 3, "R_FRACCIONAMIENTO": 11, "R_ERROR": 1}

KL = {"correo": "CORREO", "chat": "CHAT", "cfdi": "CFDI", "hoja": "COBRO"}
KN = {"correo": "Correo", "chat": "Chat", "cfdi": "CFDI (JSON)", "hoja": "Cuenta de cobro / factura"}
# Ruta de recepción de EJEMPLO por factura (no hay conectores activos): (formato, ruta)
MUESTRA = {
    "01": ("correo", "Correo"), "02": ("hoja", "Portal"), "03": ("cfdi", "API"), "04": ("chat", "Slack"),
    "05": ("hoja", "Portal"), "06": ("correo", "Correo"), "07": ("hoja", "Portal"), "08": ("cfdi", "API"),
    "09": ("chat", "WhatsApp"), "10": ("hoja", "Portal"), "11": ("chat", "WhatsApp"), "12": ("hoja", "Portal"),
    "13": ("correo", "Correo"), "14": ("chat", "Telegram"), "15": ("hoja", "Portal"), "16": ("correo", "Correo"),
    "17": ("hoja", "Portal"), "18": ("cfdi", "API"), "19": ("correo", "Correo"), "20": ("hoja", "Portal"),
    "21": ("hoja", "Portal"), "22": ("correo", "Correo"), "23": ("hoja", "Portal"), "24": ("hoja", "Portal"),
    "25": ("correo", "Correo"),
}
RUTAS = ["Correo", "Portal", "API", "WhatsApp", "Slack", "Telegram"]
CAMPOS = [  # orden de visualización
    ("beneficiary_name", "Beneficiario"), ("invoice_number", "Número de factura"), ("amount", "Monto total"),
    ("currency", "Moneda"), ("issue_date", "Fecha de emisión"), ("bank_account", "Cuenta de destino"),
    ("concept", "Concepto"),
]
_BUSQUEDA = ["amount", "currency", "issue_date", "bank_account", "invoice_number", "beneficiary_name", "concept"]
_MES = "(?:jan|ene|feb|mar|apr|abr|may|jun|jul|aug|ago|sep|oct|nov|dec|dic)"
_CODE = {"PAGAR": "P", "FRENAR": "F", "ESCALAR": "E"}


# ---------- formato ----------
def fmt_num(v) -> str:
    """1234567.5 -> '1.234.567,50' (es-CO); enteros sin decimales."""
    d = Decimal(str(v))
    s = f"{d:,.2f}" if d != d.to_integral_value() else f"{d:,.0f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_money(v, cur="") -> str:
    return f"{cur} {fmt_num(v)}".strip()


def kind_of(inv) -> tuple[str, str]:
    if inv.invoice_id in MUESTRA:
        return MUESTRA[inv.invoice_id]
    t = inv.text.lstrip()
    return ("cfdi", "API") if t.startswith("{") else ("correo", "Correo") if t.startswith("From:") else ("hoja", "Portal")


# ---------- evidencia ----------
def _num_patterns(amount: Decimal) -> list[re.Pattern]:
    ip = int(amount)
    cents = f"{amount - ip:.2f}"[2:]
    plain, us, eu = str(ip), f"{ip:,}", f"{ip:,}".replace(",", ".")
    c = [f"{us}.{cents}", f"{eu},{cents}", f"{plain}.{cents}", f"{plain},{cents}"]
    if cents == "00":
        c += [us, eu, plain]
    c.sort(key=len, reverse=True)
    return [re.compile(r"(?<![\d.,])" + re.escape(x) + r"(?!\d|[.,]\d*[1-9]|[.,]\d{3})") for x in c]


def _date_patterns(iso: str) -> list[re.Pattern]:
    y, m, d = iso.split("-")
    di, mi = str(int(d)), str(int(m))
    return [
        re.compile(re.escape(iso)),
        re.compile(rf"\b0?{di}\s+(?:de\s+)?{_MES}\w*\.?,?\s+(?:de\s+)?{y}\b", re.I),
        re.compile(rf"\b{_MES}\w*\.?\s+0?{di},?\s+{y}\b", re.I),
        re.compile(rf"\b0?{di}[/-]0?{mi}[/-]{y}\b"),
    ]


def _patterns(key: str, ex: dict) -> list[re.Pattern]:
    v = ex.get(key)
    if v in (None, ""):
        return []
    try:
        if key == "amount":
            return _num_patterns(Decimal(str(v)))
        if key == "issue_date":
            return _date_patterns(str(v))
    except Exception:
        return []
    if key == "currency":
        return [re.compile(rf"\b{re.escape(str(v))}\b", re.I)]
    return [re.compile(re.escape(str(v).strip()), re.I)]


def _first(pats, lines, taken):
    for i, ln in enumerate(lines):
        for p in pats:
            for m in p.finditer(ln):
                if not any(m.start() < b and a < m.end() for a, b, _ in taken.get(i, [])):
                    return i, m.start(), m.end()
    return None


def _name_fallback(name: str, lines, taken):
    """Línea con al menos 2 palabras del nombre (p. ej. un correo ingrid.salazar@…); marca la palabra más larga."""
    toks = [t for t in re.findall(r"\w+", name.casefold()) if len(t) >= 3]
    if len(toks) < 2:
        return None
    for i, ln in enumerate(lines):
        hits = [t for t in toks if t in ln.casefold()]
        if len(hits) >= 2:
            t = max(hits, key=len)
            a = ln.casefold().find(t)
            if not any(a < b and s < a + len(t) for s, b, _ in taken.get(i, [])):
                return i, a, a + len(t)
    return None


def build_doc(text: str, ex: dict):
    """-> (líneas con segmentos marcados, {campo: {line, needle}}). Sin coincidencia literal no hay evidencia."""
    lines = text.splitlines() or [""]
    taken: dict[int, list] = {}
    ev: dict[str, dict] = {}
    for key in _BUSQUEDA:
        hit = _first(_patterns(key, ex), lines, taken)
        if hit is None and key == "beneficiary_name":
            hit = _name_fallback(str(ex.get("beneficiary_name") or ""), lines, taken)
        if hit:
            i, a, b = hit
            taken.setdefault(i, []).append((a, b, key))
            ev[key] = {"line": i + 1, "needle": lines[i][a:b]}
    doc = []
    for i, ln in enumerate(lines):
        segs, pos = [], 0
        for a, b, k in sorted(taken.get(i, [])):
            if a > pos:
                segs.append({"t": ln[pos:a], "k": ""})
            segs.append({"t": ln[a:b], "k": k})
            pos = b
        if pos < len(ln) or not segs:
            segs.append({"t": ln[pos:], "k": ""})
        doc.append({"n": i + 1, "segs": segs})
    return doc, ev


def campos(ex: dict, ev: dict) -> list[dict]:
    out = []
    for k, label in CAMPOS:
        v = ex.get(k)
        if k == "amount" and v not in (None, ""):
            shown = fmt_money(v, ex.get("currency") or "")
        else:
            shown = str(v) if v not in (None, "") else "—"
        out.append({"k": k, "label": label, "value": shown, "ev": ev.get(k)})
    return out


# ---------- reglas / gauge / chequeos ----------
def reglas_de(policy: Policy) -> list[tuple]:
    return [r for r in REGLAS
            if not (r[0] == "R_UNICODE" and not policy.normalizar_unicode)
            and not (r[0] == "R_FRACCIONAMIENTO" and not policy.anti_fraccionamiento)]


def rule_path(rec, policy: Policy) -> list[dict]:
    lista = reglas_de(policy)
    nombres = [r[0] for r in lista]
    hit = nombres.index(rec.rule) if rec and rec.rule in nombres else None
    out = []
    for i, (n, desc, res) in enumerate(lista):
        if hit is None:
            estado = "skip"
        else:
            estado = "pass" if i < hit else "fire" if i == hit else "skip"
        txt = {"pass": "pasó", "skip": "no evaluada", "fire": "paga" if n == "OK" else rec.outcome.lower() if rec else ""}[estado]
        out.append({"n": i + 1, "nombre": n, "desc": desc, "estado": estado, "txt": txt})
    return out


def gauge(rec, policy: Policy) -> dict | None:
    usd = rec.amount_usd
    if usd is None:
        return None
    lim, umb = policy.per_payment_limit_usd, policy.approval_threshold_usd
    top = max(lim * Decimal("1.3"), usd * Decimal("1.05"), Decimal("1"))
    pct = lambda v: str(min(Decimal(100), (v / top * 100)).quantize(Decimal("0.1")))
    if usd > lim:
        txt = f"+USD {fmt_num(usd - lim)} sobre el límite"
    elif usd > umb:
        txt = "sobre el umbral"
    else:
        txt = "bajo el umbral"
    return {"usd": fmt_money(usd, "USD"), "txt": txt, "fill": pct(usd), "umb": pct(umb), "lim": pct(lim),
            "umb_txt": fmt_num(umb), "lim_txt": fmt_num(lim)}


def recheck(rec, policy: Policy, restante: Decimal) -> list[tuple]:
    """Mismo re-chequeo que approval.approve, solo para mostrarlo antes de decidir."""
    ex = rec.invoice.extraction or {}
    usd = rec.amount_usd
    return [
        ("Beneficiario registrado", bool(ex.get("beneficiary_id") in policy.beneficiaries)),
        ("Dentro del límite por pago", usd is not None and usd <= policy.per_payment_limit_usd),
        (f"Presupuesto alcanza (USD {fmt_num(restante)})", usd is not None and restante >= usd),
    ]


def segunda_lectura(rec, ex: dict) -> dict:
    sr = rec.second_read
    if not sr:
        return {"hay": False, "coincide": False}
    try:
        same = Decimal(str(sr[0])) == Decimal(str(ex.get("amount"))) and sr[1] == ex.get("currency")
    except Exception:
        same = False
    return {"hay": True, "coincide": same, "txt": fmt_money(sr[0], sr[1])}


# ---------- tarjetas y escena ----------
def estado_visible(rec, aprobacion):
    """(decisión mostrada, etiqueta): lo escalado y resuelto por una persona toma su desenlace."""
    if rec.outcome == "ESCALAR" and aprobacion:
        return ("PAGAR", "Aprobada · borrador") if aprobacion.outcome == "APROBADO" else ("FRENAR", "Rechazada")
    return rec.outcome, rec.outcome


def card(rec, aprobacion=None) -> dict:
    ex = rec.invoice.extraction or {}
    kind, route = kind_of(rec.invoice)
    d, lab = estado_visible(rec, aprobacion)
    cur = ex.get("currency") or ""
    return {
        "id": rec.invoice.invoice_id, "file": rec.invoice.filename, "kind": kind, "kl": KL[kind], "kn": KN[kind],
        "route": route, "name": ex.get("beneficiary_name") or "—", "cur": cur,
        "amt": fmt_money(ex.get("amount"), "") if ex.get("amount") else "—",
        "amt_full": fmt_money(ex.get("amount"), cur) if ex.get("amount") else "—",
        "usd": fmt_money(rec.amount_usd, "USD") if rec.amount_usd is not None else "",
        "issue": ex.get("issue_date") or "", "num": ex.get("invoice_number") or "",
        "outcome": rec.outcome, "rule": rec.rule, "d": d, "label": lab,
        "req": rec.invoice.requested_by,
        "q": " ".join([rec.invoice.invoice_id, rec.invoice.filename, ex.get("beneficiary_name") or "",
                       ex.get("invoice_number") or ""]).casefold(),
    }


def scene_items(records, policy: Policy, restante: Decimal, aprobaciones: dict) -> list[dict]:
    """Facturas reales para flow3d: {id,k,d,r,i,s,t} (+ n, a, o para la línea en vivo)."""
    out = []
    for r in records:
        ex = r.invoice.extraction or {}
        kind, _ = kind_of(r.invoice)
        ap = aprobaciones.get(r.pk)
        t = ""
        if r.rule == "R_SOSPECHA":
            t = "inj"
        elif r.outcome == "ESCALAR":
            ok = (ap.outcome == "APROBADO") if ap else all(c[1] for c in recheck(r, policy, restante))
            t = "draft" if ok else "block"
        i = BASE13.index(r.rule) + 1 if r.rule in BASE13 else ANILLO_EXTRA.get(r.rule, 1)
        out.append({"id": r.invoice.invoice_id, "k": kind, "d": _CODE[r.outcome], "r": r.rule, "i": i,
                    "s": 1 if r.second_read else 0, "t": t,
                    "n": ex.get("beneficiary_name") or "—",
                    "a": fmt_money(ex.get("amount"), ex.get("currency") or "") if ex.get("amount") else "—",
                    "o": r.outcome})
    return out
