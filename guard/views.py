import csv
import hashlib
import io
import json
import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .approval import approve, reject
from .data import load_expected, load_policy
from .domain import Extraction, Policy
from .engine import Ledger, allowed_to_pay
from .explain import explain
from . import receipt as rcpt
from . import ui
from .models import Approval, DecisionRecord, Event, Invoice, PolicyVersion, UsedNonce
from .services import apply_mandato_v2, correct_field, current_policy, emit, run_arena, ensure_receipts, process_all, process_next, process_text, save_policy, spent_usd

DECISIONES = ("PAGAR", "FRENAR", "ESCALAR")
ISO3 = re.compile(r"^[A-Za-z]{3}$")
MAX_BODY = 20480  # bytes
CAMPOS_FORM = [(k, l) for k, l in ui.CAMPOS if k in ("amount", "currency", "issue_date", "invoice_number", "concept")]
ETIQUETA_CAMPO = dict(ui.CAMPOS)


def ensure_processed() -> PolicyVersion:
    pv = current_policy()
    if not DecisionRecord.objects.filter(policy_version=pv).exists():
        process_all(pv)
    ensure_receipts(pv)
    return pv


def _aprobacion(rec: DecisionRecord) -> Approval | None:
    try:
        return rec.approval
    except Approval.DoesNotExist:
        return None


def _records(pv: PolicyVersion):
    return list(
        DecisionRecord.objects.filter(policy_version=pv)
        .select_related("invoice", "policy_version")
        .order_by("invoice__invoice_id")
    )


def _extraccion(rec: DecisionRecord) -> dict:
    return rec.invoice.extraction or {}


def _cuenta_maestra(policy: Policy, ex: dict) -> dict:
    """Cuenta del registro maestro; la que pedía la factura solo se muestra tachada."""
    ben = policy.beneficiaries.get(ex.get("beneficiary_id") or "")
    maestra = str((ben or {}).get("cuenta") or "")
    factura = str(ex.get("bank_account") or "")
    return {
        "maestra": maestra,
        "factura": factura,
        "distinta": bool(maestra and factura and factura.strip() != maestra.strip()),
    }


def _pagos_indebidos(records, policy: Policy) -> int:
    # reconstruye el ledger en orden, igual que run_batch, y pregunta al oraculo
    ledger = Ledger(policy.period_budget_remaining_usd, [])
    malos = 0
    for rec in records:
        if rec.outcome != "PAGAR":
            continue
        x = Extraction.from_dict(rec.invoice.extraction)
        if not allowed_to_pay(x, policy, ledger):
            malos += 1
        if rec.amount_usd is not None:
            ledger.remaining_usd -= rec.amount_usd
        ledger.paid.append(x)
    return malos


def _aprobaciones(records) -> dict:
    return {a.decision_id: a for a in Approval.objects.filter(decision__in=[r.pk for r in records])}


def _contexto_base(pv):
    policy = Policy(pv.raw, pv.version)
    records = _records(pv)
    aprob = _aprobaciones(records)
    restante = policy.period_budget_remaining_usd - spent_usd(pv)
    mensual = Decimal(str(policy.raw["presupuesto"]["mensual_usd"]))
    gastado = mensual - restante
    pct = min(Decimal(100), max(Decimal(0), gastado / mensual * 100)) if mensual else Decimal(0)
    return policy, records, aprob, restante, {
        "restante_txt": ui.fmt_num(restante), "mensual_txt": ui.fmt_num(mensual),
        "gastado_txt": ui.fmt_num(gastado), "gastado_pct": str(pct.quantize(Decimal("0.1"))),
    }


def _doble_lectura(records) -> dict:
    ok = no = mal = 0
    for r in records:
        sr = ui.segunda_lectura(r, r.invoice.extraction or {})
        if not sr["hay"]:
            no += 1
        elif sr["coincide"]:
            ok += 1
        else:
            mal += 1
    return {"coinciden": ok, "abstiene": no, "contradice": mal}


def board(request):
    pv = ensure_processed()
    policy, records, aprob, restante, presup = _contexto_base(pv)
    counts = {d: sum(1 for r in records if r.outcome == d) for d in DECISIONES}
    total = len(records)
    autonomia = round((counts["PAGAR"] + counts["FRENAR"]) / total * 100) if total else 0
    lanes = [{"key": d, "tickets": [ui.card(r, aprob.get(r.pk)) for r in records if r.outcome == d]}
             for d in DECISIONES]
    # la coincidencia con el esperado solo tiene sentido con la politica dorada
    coincide = None
    if pv.raw == load_policy().raw:
        esperado = load_expected()
        coincide = sum(1 for r in records if esperado.get(r.invoice.invoice_id) == r.outcome)
    pendientes = sum(1 for r in records if r.outcome == "ESCALAR" and r.pk not in aprob)
    ctx = {
        "pv": pv,
        "lanes": lanes,
        "counts": counts,
        "total": total,
        "autonomia": autonomia,
        "indebidos": _pagos_indebidos(records, policy),
        "coincide": coincide,
        "restante": restante,
        "presup": presup,
        "doble": _doble_lectura(records),
        "pendientes": pendientes,
        "escena": ui.scene_items(records, policy, restante, aprob),
        "arena": pv.arena_runs.order_by("-created_at", "-id").first(),
    }
    return render(request, "guard/board.html", ctx)


def library(request):
    pv = ensure_processed()
    policy, records, aprob, restante, presup = _contexto_base(pv)
    cards = [ui.card(r, aprob.get(r.pk)) for r in records]
    sel_id = request.GET.get("id") or ("25" if any(c["id"] == "25" for c in cards) else cards[0]["id"])
    rec = next((r for r in records if r.invoice.invoice_id == sel_id), records[0])
    sel = next(c for c in cards if c["id"] == rec.invoice.invoice_id)
    ex = rec.invoice.extraction or {}
    doc, ev = ui.build_doc(rec.invoice.text, ex)
    paso = request.GET.get("paso", "2")
    paso = int(paso) if paso in ("1", "2", "3", "4", "5") else 2
    ap = aprob.get(rec.pk)
    pagadas = [r for r in records if r.outcome == "PAGAR"]
    campos = ui.campos(ex, ev)
    pend = sum(1 for r in records if r.outcome == "ESCALAR" and r.pk not in aprob)
    ctx = {
        "pv": pv, "cards": cards, "sel": sel, "rec": rec, "doc": doc, "campos": campos,
        "con_evidencia": sum(1 for c in campos if c["ev"]), "total_campos": len(campos),
        "paso": paso, "rutas": [{"n": r, "c": sum(1 for c in cards if c["route"] == r)} for r in ui.RUTAS],
        "lectura": ui.segunda_lectura(rec, ex), "reglas": ui.rule_path(rec, policy),
        "gauge": ui.gauge(rec, policy), "aprobacion": ap,
        "sospechoso": bool(ex.get("suspicious")) or rec.rule == "R_SOSPECHA",
        "kpi": {"docs": len(cards), "por_confirmar": _doble_lectura(records)["abstiene"], "pend": pend,
                "pagadas_n": len(pagadas),
                "pagadas_usd": ui.fmt_num(sum((r.amount_usd or Decimal(0)) for r in pagadas))},
        "pasos": ["Documento", "Extracción", "Doble llave", "Reglas", "Decisión"],
    }
    return render(request, "guard/library.html", ctx)


def invoice_detail(request, invoice_id: str, tamper_error: str = ""):
    pv = ensure_processed()
    policy = Policy(pv.raw, pv.version)
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id)
    record = (
        DecisionRecord.objects.filter(invoice=invoice, policy_version=pv)
        .select_related("policy_version")
        .first()
    )
    ex = invoice.extraction or {}
    doc, ev = ui.build_doc(invoice.text, ex)
    ctx = {
        "pv": pv,
        "invoice": invoice,
        "record": record,
        "doc": doc,
        "reglas": ui.rule_path(record, policy) if record else [],
        "gauge": ui.gauge(record, policy) if record else None,
        "campos": ui.campos(ex, ev),
        "cuenta": _cuenta_maestra(policy, ex),
        "facts_json": json.dumps(record.facts, indent=2, ensure_ascii=False, default=str) if record else "",
        "second_read": record.second_read if record else None,
        "aprobacion": _aprobacion(record) if record else None,
        "tamper_error": tamper_error,
        "card": ui.card(record, _aprobacion(record)) if record else None,
        "campos_form": CAMPOS_FORM,
        "correcciones": [
            {"c": c, "campo": ETIQUETA_CAMPO.get(c.field, c.field)}
            for c in invoice.corrections.order_by("-created_at", "-id")
        ],
    }
    if record and record.receipt:
        ok, motivo = rcpt.verify(record.receipt, check_nonce=False)
        ctx.update(receipt=record.receipt, receipt_ok=ok, receipt_motivo=motivo,
                   receipt_usado=UsedNonce.objects.filter(nonce=record.receipt.get("nonce")).exists())
    if record:
        a = _aprobacion(record)
        ctx["draft_json"] = json.dumps(a.draft, indent=2, ensure_ascii=False) if a and a.draft else ""
    return render(request, "guard/detail.html", ctx)


@require_POST
def corregir_campo(request, invoice_id: str):
    """Corrección humana de un campo extraído: re-decide la factura y regenera su recibo."""
    ensure_processed()
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id)
    field = (request.POST.get("campo") or "").strip()
    value = request.POST.get("valor") or ""
    motivo = request.POST.get("motivo") or ""
    actor = (request.POST.get("actor") or "").strip() or invoice.requested_by
    try:
        rec = correct_field(invoice.invoice_id, field, value, actor, motivo)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("invoice_detail", invoice_id=invoice_id)
    messages.success(
        request,
        f"Factura {invoice.invoice_id}: «{ETIQUETA_CAMPO.get(field, field)}» corregido a {value.strip()}; "
        f"nueva decisión {rec.outcome} ({rec.rule}) y recibo regenerado.",
    )
    return redirect("invoice_detail", invoice_id=invoice_id)


@require_POST
def correr_arena(request):
    pv = ensure_processed()
    r = run_arena(pv)
    messages.success(request, f"Arena corrida: {r.indebidos} pagos indebidos de {r.total} ataques (política v{pv.version}).")
    return redirect("board")


@require_POST
def aplicar_mandato_v2(request):
    ensure_processed()
    nueva = apply_mandato_v2()
    messages.success(request, f"Mandato v2 aplicado como política v{nueva.version}; 25 facturas reprocesadas.")
    return redirect("rules")


@require_POST
def tamper_receipt(request, invoice_id: str):
    """Demo: intenta aprobar con el monto del recibo cambiado; el guardián debe rechazarlo."""
    pv = ensure_processed()
    record = get_object_or_404(DecisionRecord, invoice__invoice_id=invoice_id, policy_version=pv)
    try:
        nuevo = Decimal((request.POST.get("monto") or "1").strip())
    except InvalidOperation:
        messages.error(request, "Monto inválido.")
        return redirect("invoice_detail", invoice_id=invoice_id)
    if not record.receipt:
        return redirect("invoice_detail", invoice_id=invoice_id)
    alterado = {**record.receipt, "amount": str(nuevo)}
    try:
        approve(record, "demo@guardian", "demo alteración", receipt=alterado)
    except ValueError as e:
        return invoice_detail(request, invoice_id, tamper_error=str(e))
    return redirect("invoice_detail", invoice_id=invoice_id)  # ponytail: inalcanzable salvo monto igual al decidido


def _form_valores(raw: dict, data: dict | None = None) -> dict:
    r = raw["reglas_pago"]
    if data is None:
        return {
            "limite_por_pago": str(r["limite_por_pago_usd"]),
            "umbral_aprobacion": str(r["umbral_aprobacion_humana_usd"]),
            "monedas": ", ".join(r["monedas_permitidas"]),
            "tolerancia": str(r["tolerancia_monto_contrato_pct"]),
        }
    return data


def _decimal(campo: str, valor: str, errores: list, permitir_cero=False) -> Decimal | None:
    try:
        d = Decimal(valor)
    except InvalidOperation:
        errores.append(f"{campo}: «{valor}» no es un número.")
        return None
    if d < 0 or (d == 0 and not permitir_cero):
        errores.append(f"{campo}: debe ser mayor a 0.")
        return None
    return d


def rules(request):
    pv = ensure_processed()
    if request.method == "POST":
        datos = {
            "limite_por_pago": (request.POST.get("limite_por_pago") or "").strip(),
            "umbral_aprobacion": (request.POST.get("umbral_aprobacion") or "").strip(),
            "monedas": (request.POST.get("monedas") or "").strip(),
            "tolerancia": (request.POST.get("tolerancia") or "").strip(),
        }
        errores = []
        limite = _decimal("Límite por pago", datos["limite_por_pago"], errores)
        umbral = _decimal("Umbral de aprobación", datos["umbral_aprobacion"], errores)
        tolerancia = _decimal("Tolerancia de contrato", datos["tolerancia"], errores, permitir_cero=True)
        monedas = [m.strip().upper() for m in datos["monedas"].split(",") if m.strip()]
        if not monedas:
            errores.append("Monedas permitidas: indique al menos una.")
        for m in monedas:
            if not ISO3.match(m):
                errores.append(f"Moneda «{m}»: debe ser un código ISO de 3 letras.")
        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, "guard/rules.html", _rules_ctx(pv, datos))
        raw = deepcopy(pv.raw)
        raw["reglas_pago"]["limite_por_pago_usd"] = str(limite)
        raw["reglas_pago"]["umbral_aprobacion_humana_usd"] = str(umbral)
        raw["reglas_pago"]["monedas_permitidas"] = monedas
        raw["reglas_pago"]["tolerancia_monto_contrato_pct"] = str(tolerancia)
        nueva = save_policy(raw)
        process_all(nueva)
        messages.success(request, f"Reglas guardadas en la versión v{nueva.version}; 25 facturas reprocesadas.")
        return redirect("board")
    return render(request, "guard/rules.html", _rules_ctx(pv, _form_valores(pv.raw)))


def _param_regla(nombre: str, policy: Policy) -> str:
    return {
        "R_LIMITE": f"USD {ui.fmt_num(policy.per_payment_limit_usd)}",
        "R_UMBRAL": f"USD {ui.fmt_num(policy.approval_threshold_usd)}",
        "R_PRESUPUESTO": f"USD {ui.fmt_num(policy.period_budget_remaining_usd)}",
        "R_MONEDA": ", ".join(sorted(policy.allowed_currencies)),
        "R_FECHA": f"{policy.max_age_days} días",
        "R_CONTRATO": f"{policy.contract_tolerance_pct} %",
        "R_BENEFICIARIO": "registro", "R_CUENTA": "registro", "R_DOBLE_LECTURA": "coincidir",
    }.get(nombre, "—")


def _rules_ctx(pv: PolicyVersion, form: dict) -> dict:
    policy = Policy(pv.raw, pv.version)
    cuentan = {}
    for r in DecisionRecord.objects.filter(policy_version=pv).values_list("rule", flat=True):
        cuentan[r] = cuentan.get(r, 0) + 1
    tabla = [{"n": i + 1, "nombre": n, "desc": d, "res": res, "param": _param_regla(n, policy),
              "facturas": cuentan.get(n, 0)} for i, (n, d, res) in enumerate(ui.reglas_de(policy))]
    return {"pv": pv, "form": form, "versiones": _versiones(pv), "tabla": tabla, "total_reglas": len(tabla)}


def _versiones(pv: PolicyVersion) -> list[dict]:
    out = []
    for v in PolicyVersion.objects.order_by("-version"):
        r = v.raw["reglas_pago"]
        out.append({"version": v.version, "created_at": v.created_at, "actual": v.pk == pv.pk,
                    "limite": ui.fmt_num(r["limite_por_pago_usd"]), "umbral": ui.fmt_num(r["umbral_aprobacion_humana_usd"]),
                    "v2": bool(r.get("anti_fraccionamiento") or r.get("normalizar_unicode"))})
    return out


def inbox(request):
    pv = ensure_processed()
    policy, records, aprob, restante, presup = _contexto_base(pv)
    pendientes = [{"rec": r, "card": ui.card(r), "checks": ui.recheck(r, policy, restante)}
                  for r in records if r.outcome == "ESCALAR" and r.pk not in aprob]
    resueltas = [{"rec": r, "card": ui.card(r, aprob[r.pk]), "ap": aprob[r.pk]}
                 for r in records if r.pk in aprob]
    ultimo = max((x for x in resueltas if x["ap"].draft), key=lambda x: x["ap"].created_at, default=None)
    n_esc = sum(1 for r in records if r.outcome == "ESCALAR")
    ctx = {
        "pv": pv, "pendientes": pendientes, "resueltas": resueltas, "presup": presup,
        "n_esc": n_esc, "n_ok": sum(1 for x in resueltas if x["ap"].outcome == "APROBADO"),
        "n_rech": sum(1 for x in resueltas if x["ap"].outcome == "RECHAZADO"),
        "draft_json": json.dumps(ultimo["ap"].draft, indent=2, ensure_ascii=False) if ultimo else "",
        "draft_de": ultimo["card"]["id"] if ultimo else "",
        "cuenta": _cuenta_maestra(policy, _extraccion(ultimo["ap"].decision)) if ultimo else None,
    }
    return render(request, "guard/inbox.html", ctx)


@require_POST
def decide_approval(request, record_id: int):
    pv = ensure_processed()
    record = get_object_or_404(DecisionRecord, pk=record_id, policy_version=pv)
    accion = request.POST.get("action")
    approver = (request.POST.get("approver") or "cfo@lumbre.example").strip() or "cfo@lumbre.example"
    nota = request.POST.get("note") or ""
    try:
        if accion == "aprobar":
            approve(record, approver, nota)
        elif accion == "rechazar":
            reject(record, approver, nota)
        else:
            raise ValueError("acción desconocida; use aprobar o rechazar")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("inbox")
    if accion == "aprobar":
        messages.success(request, f"Factura {record.invoice.invoice_id} aprobada; borrador generado (no ejecutado).")
        return redirect("invoice_detail", invoice_id=record.invoice.invoice_id)
    messages.success(request, f"Factura {record.invoice.invoice_id} rechazada.")
    return redirect("inbox")


def log(request):
    pv = ensure_processed()
    records = _records(pv)
    if request.GET.get("format") == "json":
        aprob = _aprobaciones(records)
        resp = HttpResponse(
            json.dumps([_fila_json(r, aprob) for r in records], ensure_ascii=False, default=str),
            content_type="application/json",
        )
        resp["Content-Disposition"] = 'attachment; filename="registro.json"'
        return resp
    filas = [_fila_log(r) for r in records]
    if request.GET.get("format") == "csv":
        return _csv_response(filas)
    return render(request, "guard/log.html", {"pv": pv, "filas": filas, "eventos": _eventos(records), "registros": records})


def _eventos(records) -> list[dict]:
    """Línea de tiempo de auditoría con hash encadenado (sha256 del evento + hash previo; demostración)."""
    crudos = []
    for r in records:
        ex = _extraccion(r)
        crudos.append((r.created_at, "decisión", r.invoice.invoice_id,
                       f"{r.outcome} · {r.rule} · {ex.get('beneficiary_name') or '—'}", r.policy_version.version))
        a = _aprobacion(r)
        if a:
            crudos.append((a.created_at, "aprobación" if a.outcome == "APROBADO" else "rechazo", r.invoice.invoice_id,
                           f"{a.outcome.lower()} por {a.approver}", r.policy_version.version))
    crudos.sort(key=lambda e: (e[0], e[2]))
    prev, out = "", []
    for ts, ev, inv, det, v in crudos:
        prev = hashlib.sha256("|".join([prev, ts.isoformat(), ev, inv, det, str(v)]).encode()).hexdigest()
        out.append({"hora": timezone.localtime(ts).strftime("%H:%M:%S"), "evento": ev, "factura": inv,
                    "detalle": det, "version": v, "hash": prev[:8]})
    return out


def _fila_log(rec: DecisionRecord) -> dict:
    ex = _extraccion(rec)
    a = _aprobacion(rec)
    return {
        "invoice_id": rec.invoice.invoice_id,
        "beneficiario": ex.get("beneficiary_name") or "",
        "monto": str(ex.get("amount") or ""),
        "moneda": ex.get("currency") or "",
        "monto_usd": "" if rec.amount_usd is None else str(rec.amount_usd),
        "decision": rec.outcome,
        "regla": rec.rule,
        "explicacion": rec.explanation,
        "aprobacion": a.outcome if a else "",
        "aprobador": a.approver if a else "",
        "nota": a.note if a else "",
        "policy_version": rec.policy_version.version,
    }


COLUMNAS = [
    "invoice_id", "beneficiario", "monto", "moneda", "monto_usd", "decision",
    "regla", "explicacion", "aprobacion", "aprobador", "nota", "policy_version",
]


def _evidencia(rec: DecisionRecord) -> dict:
    """{campo: línea del texto original donde aparece el valor} o null si no aparece literal."""
    ex = _extraccion(rec)
    _, ev = ui.build_doc(rec.invoice.text, ex)
    out = {}
    for k in [c for c, _ in ui.CAMPOS] + [k for k in ex if k not in dict(ui.CAMPOS)]:
        hit = ev.get(k)
        out[k] = hit["line"] if hit else None
    return out


def _fila_json(rec: DecisionRecord, aprob: dict) -> dict:
    a = aprob.get(rec.pk)
    return {
        "invoice_id": rec.invoice.invoice_id,
        "policy_version": rec.policy_version.version,
        "outcome": rec.outcome,
        "rule": rec.rule,
        "facts": rec.facts,
        "explanation": rec.explanation,
        "extraction": _extraccion(rec),
        "evidence": _evidencia(rec),
        "second_read": rec.second_read,
        "receipt_sig": (rec.receipt or {}).get("sig"),
        "approval": {
            "outcome": a.outcome if a else None,
            "approver": a.approver if a else None,
            "note": a.note if a else None,
            "requested_by": rec.invoice.requested_by,
        },
    }


def _csv_response(filas: list[dict]) -> HttpResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNAS)
    for f in filas:
        w.writerow([f[c] for c in COLUMNAS])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="registro.csv"'
    return resp


@require_POST
def reset_demo(request):
    Approval.objects.all().delete()
    DecisionRecord.objects.all().delete()
    Invoice.objects.all().delete()
    PolicyVersion.objects.all().delete()
    pv = save_policy(load_policy().raw)
    process_all(pv)
    messages.success(request, "Demo reiniciada: política v1 y 25 facturas reprocesadas.")
    return redirect("board")


@csrf_exempt
@require_POST
def api_evaluate(request):
    # ponytail: demo publica; token por cabecera antes de un piloto.
    if len(request.body) > MAX_BODY:
        return JsonResponse({"error": f"cuerpo demasiado grande; maximo {MAX_BODY} bytes"}, status=413)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "el cuerpo no es JSON valido"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "se esperaba un objeto JSON con la clave text"}, status=400)
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return JsonResponse({"error": "text debe ser una cadena no vacia"}, status=400)
    d = process_text(text, "api")
    emit("prueba", invoice_id="api", outcome=d.outcome, rule=d.rule,
         amount_usd=d.amount_usd, policy_version=current_policy().version)
    return JsonResponse(
        {
            "outcome": d.outcome,
            "rule": d.rule,
            # explain() solo usa el Decision, no la extraccion
            "explanation": explain(d, None),
            "policy_version": current_policy().version,
            "facts": d.facts,
        }
    )


def _kpis(pv: PolicyVersion) -> dict:
    """KPIs de la política actual para /api/eventos."""
    policy = Policy(pv.raw, pv.version)
    records = _records(pv)
    counts = {d: sum(1 for r in records if r.outcome == d) for d in DECISIONES}
    total = len(records)
    autonomia = round((counts["PAGAR"] + counts["FRENAR"]) / total * 100) if total else 0
    restante = policy.period_budget_remaining_usd - spent_usd(pv)
    return {
        "pagar": counts["PAGAR"],
        "frenar": counts["FRENAR"],
        "escalar": counts["ESCALAR"],
        "autonomia_pct": autonomia,
        "indebidos": _pagos_indebidos(records, policy),
        "restante_usd": str(restante),
        "policy_version": pv.version,
    }


def api_eventos(request):
    """GET /api/eventos?after=<id> -> {events:[...], kpis:{...}}"""
    after = request.GET.get("after", "0")
    try:
        after_id = int(after)
    except (ValueError, TypeError):
        after_id = 0
    pv = current_policy()
    qs = (
        Event.objects.filter(id__gt=after_id)
        .order_by("id")[:50]
    )
    events = [
        {
            "id": e.id,
            "kind": e.kind,
            "invoice_id": e.invoice_id,
            "outcome": e.outcome,
            "rule": e.rule,
            "amount_usd": str(e.amount_usd) if e.amount_usd is not None else None,
            "message": e.message,
            "created_at": e.created_at.isoformat(),
        }
        for e in qs
    ]
    return JsonResponse({"events": events, "kpis": _kpis(pv)})


@require_POST
def demo_en_vivo(request):
    """POST /demo/en-vivo/ -> guarda la política actual sin procesar y redirige a '/'."""
    pv = current_policy()
    save_policy(pv.raw)
    return redirect("/")


@require_POST
def demo_en_vivo_siguiente(request):
    """POST /demo/en-vivo/siguiente/ -> procesa la siguiente factura; retorna JSON {done, event}."""
    pv = current_policy()
    rec = process_next(pv)
    if rec is None:
        return JsonResponse({"done": True, "event": None})
    # buscar el event recién emitido para esta factura y política
    ev = (
        Event.objects.filter(kind="decision", invoice_id=rec.invoice.invoice_id,
                             policy_version=pv.version)
        .order_by("-id")
        .first()
    )
    event_data = None
    if ev:
        event_data = {
            "id": ev.id,
            "kind": ev.kind,
            "invoice_id": ev.invoice_id,
            "outcome": ev.outcome,
            "rule": ev.rule,
            "amount_usd": str(ev.amount_usd) if ev.amount_usd is not None else None,
            "message": ev.message,
            "created_at": ev.created_at.isoformat(),
        }
    # ¿quedan facturas por decidir?
    done_count = DecisionRecord.objects.filter(policy_version=pv).count()
    total_count = Invoice.objects.count()
    done = done_count >= total_count
    return JsonResponse({"done": done, "event": event_data})
