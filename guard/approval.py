# ponytail: re-chequeo de limites duros al aprobar (idea de imprest); la cuenta SIEMPRE del registro maestro.
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from .domain import Policy
from .models import Approval, DecisionRecord
from .services import spent_usd

CENT = Decimal("0.01")
RAILS = {"US": "ACH", "CO": "BRE_B", "MX": "SPEI"}


def _require_note(note: str):
    if not note or not note.strip():
        raise ValueError("la nota de aprobacion es obligatoria")


def _require_escalable(record: DecisionRecord):
    if record.outcome != "ESCALAR":
        raise ValueError("solo se puede decidir sobre un registro ESCALAR")
    if Approval.objects.filter(decision=record).exists():
        raise ValueError("este registro ya tiene una aprobacion; no se puede decidir dos veces")


def _extraction(record: DecisionRecord) -> dict:
    return record.invoice.extraction or {}


def approve(record: DecisionRecord, approver: str, note: str) -> dict:
    _require_escalable(record)
    _require_note(note)
    ex = _extraction(record)
    pv = record.policy_version
    policy = Policy(pv.raw, pv.version)
    ben_id = ex.get("beneficiary_id")
    if not ben_id or ben_id not in policy.beneficiaries:
        raise ValueError("no se puede aprobar: beneficiario no registrado; darlo de alta primero")
    ben = policy.beneficiaries[ben_id]
    currency = str(ex.get("currency") or "")
    if currency not in policy.allowed_currencies:
        raise ValueError(f"no se puede aprobar: moneda {currency} no permitida")
    amount = Decimal(str(ex.get("amount") or "0"))
    usd = (amount * policy.fx[currency]).quantize(CENT, ROUND_HALF_UP)
    if usd > policy.per_payment_limit_usd:
        raise ValueError(
            f"no se puede aprobar: USD {usd} supera el limite por pago de USD {policy.per_payment_limit_usd}"
        )
    restante = policy.period_budget_remaining_usd - spent_usd(pv)
    if restante < usd:
        raise ValueError(
            f"no se puede aprobar: presupuesto insuficiente; restan USD {restante} y se requieren USD {usd}"
        )
    draft = {
        "object": "transfer_draft",
        "status": "draft_not_executed",
        "amount_minor": int((amount).quantize(CENT, ROUND_HALF_UP) * 100),
        "currency": currency,
        "beneficiary_id": ben_id,
        "beneficiary_account": ben["cuenta"],
        "rail": RAILS.get(ben.get("pais"), "SWIFT"),
        "invoice_id": record.invoice.invoice_id,
        "policy_version": pv.version,
        "approved_by": approver,
        "approval_note": note.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    Approval.objects.create(
        decision=record, outcome="APROBADO", note=note.strip(), approver=approver, draft=draft
    )
    return draft


def reject(record: DecisionRecord, approver: str, note: str) -> Approval:
    _require_escalable(record)
    _require_note(note)
    return Approval.objects.create(
        decision=record, outcome="RECHAZADO", note=note.strip(), approver=approver
    )
