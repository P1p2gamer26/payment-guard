import csv
import io
import json
import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .approval import approve, reject
from .data import load_expected, load_policy
from .domain import Extraction, Policy
from .engine import RULES, Ledger, allowed_to_pay
from .explain import explain
from .models import Approval, DecisionRecord, Invoice, PolicyVersion
from .services import current_policy, process_all, process_text, save_policy, spent_usd

DECISIONES = ("PAGAR", "FRENAR", "ESCALAR")
ISO3 = re.compile(r"^[A-Za-z]{3}$")
MAX_BODY = 20480  # bytes


def ensure_processed() -> PolicyVersion:
    pv = current_policy()
    if not DecisionRecord.objects.filter(policy_version=pv).exists():
        process_all(pv)
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


def board(request):
    pv = ensure_processed()
    policy = Policy(pv.raw, pv.version)
    records = _records(pv)
    counts = {d: sum(1 for r in records if r.outcome == d) for d in DECISIONES}
    total = len(records)
    autonomia = round((counts["PAGAR"] + counts["FRENAR"]) / total * 100) if total else 0
    lanes = []
    for d in DECISIONES:
        tickets = []
        for r in records:
            if r.outcome != d:
                continue
            ex = _extraccion(r)
            tickets.append(
                {
                    "id": r.invoice.invoice_id,
                    "beneficiario": ex.get("beneficiary_name") or "—",
                    "monto": ex.get("amount") or "—",
                    "moneda": ex.get("currency") or "",
                    "regla": r.rule,
                    "outcome": r.outcome,
                }
            )
        lanes.append({"key": d, "tickets": tickets})
    # la coincidencia con el esperado solo tiene sentido con la politica dorada
    coincide = None
    if pv.raw == load_policy().raw:
        esperado = load_expected()
        coincide = sum(1 for r in records if esperado.get(r.invoice.invoice_id) == r.outcome)
    ctx = {
        "pv": pv,
        "lanes": lanes,
        "counts": counts,
        "total": total,
        "autonomia": autonomia,
        "indebidos": _pagos_indebidos(records, policy),
        "coincide": coincide,
        "restante": policy.period_budget_remaining_usd - spent_usd(pv),
    }
    return render(request, "guard/board.html", ctx)


def invoice_detail(request, invoice_id: str):
    pv = ensure_processed()
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id)
    record = (
        DecisionRecord.objects.filter(invoice=invoice, policy_version=pv)
        .select_related("policy_version")
        .first()
    )
    reglas = _rule_path(record)
    ctx = {
        "pv": pv,
        "invoice": invoice,
        "record": record,
        "reglas": reglas,
        "facts_json": json.dumps(record.facts, indent=2, ensure_ascii=False, default=str) if record else "",
        "second_read": record.second_read if record else None,
        "aprobacion": _aprobacion(record) if record else None,
    }
    if record:
        a = _aprobacion(record)
        ctx["draft_json"] = json.dumps(a.draft, indent=2, ensure_ascii=False) if a and a.draft else ""
    return render(request, "guard/detail.html", ctx)


def _rule_path(record) -> list[dict]:
    """Reglas en orden; la que disparo queda .hit y las siguientes sin evaluar."""
    hit = record.rule.lower() if record else None
    hit_index = next((i for i, r in enumerate(RULES) if r.__name__ == hit), None)
    todo_evaluado = record is not None and record.rule == "OK"
    out = []
    for i, rule in enumerate(RULES):
        if hit_index is None:
            estado = "evaluada" if (record is not None and todo_evaluado) else "no-evaluada"
        elif i < hit_index:
            estado = "evaluada"
        elif i == hit_index:
            estado = "hit"
        else:
            estado = "no-evaluada"
        out.append({"nombre": rule.__name__, "estado": estado})
    return out


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
            return render(
                request,
                "guard/rules.html",
                {"pv": pv, "form": datos, "versiones": _versiones(pv)},
            )
        raw = deepcopy(pv.raw)
        raw["reglas_pago"]["limite_por_pago_usd"] = str(limite)
        raw["reglas_pago"]["umbral_aprobacion_humana_usd"] = str(umbral)
        raw["reglas_pago"]["monedas_permitidas"] = monedas
        raw["reglas_pago"]["tolerancia_monto_contrato_pct"] = str(tolerancia)
        nueva = save_policy(raw)
        process_all(nueva)
        messages.success(request, f"Reglas guardadas en la versión v{nueva.version}; 25 facturas reprocesadas.")
        return redirect("board")
    return render(
        request,
        "guard/rules.html",
        {"pv": pv, "form": _form_valores(pv.raw), "versiones": _versiones(pv)},
    )


def _versiones(pv: PolicyVersion) -> list[dict]:
    return [
        {"version": v.version, "created_at": v.created_at, "actual": v.pk == pv.pk}
        for v in PolicyVersion.objects.order_by("-version")
    ]


def inbox(request):
    pv = ensure_processed()
    pendientes = (
        DecisionRecord.objects.filter(policy_version=pv, outcome="ESCALAR", approval__isnull=True)
        .select_related("invoice")
        .order_by("invoice__invoice_id")
    )
    return render(request, "guard/inbox.html", {"pv": pv, "pendientes": pendientes})


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
    filas = [_fila_log(r) for r in records]
    if request.GET.get("format") == "csv":
        return _csv_response(filas)
    return render(request, "guard/log.html", {"pv": pv, "filas": filas, "registros": records})


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
