"""Recibo firmado (HMAC-SHA256): el guardián solo emite el borrador si el recibo de la decisión es íntegro, vigente y de un solo uso."""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from django.conf import settings

from .domain import Policy

FIELDS = ("invoice_id", "amount", "currency", "beneficiary_id", "beneficiary_account",
          "outcome", "rule", "policy_version", "nonce", "expires_at")


def _key() -> bytes:
    # ponytail: clave derivada de SECRET_KEY; rotar SECRET_KEY invalida recibos vivos
    return hashlib.sha256(b"payment-guard-receipt:" + settings.SECRET_KEY.encode()).digest()


def _mac(payload: dict) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(_key(), canon.encode(), hashlib.sha256).hexdigest()


def sign(record) -> dict:
    ex = record.invoice.extraction or {}
    pv = record.policy_version
    ben_id = ex.get("beneficiary_id")
    ben = Policy(pv.raw, pv.version).beneficiaries.get(ben_id)
    payload = {
        "invoice_id": record.invoice.invoice_id,
        "amount": str(ex.get("amount", "")),
        "currency": ex.get("currency") or "",
        "beneficiary_id": ben_id,
        "beneficiary_account": ben["cuenta"] if ben else "",
        "outcome": record.outcome,
        "rule": record.rule,
        "policy_version": pv.version,
        "nonce": secrets.token_hex(16),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
    }
    return {**payload, "sig": _mac(payload)}


def verify(receipt, now=None, check_nonce=True) -> tuple[bool, str]:
    from .models import UsedNonce
    try:
        payload = {k: receipt[k] for k in FIELDS}
        sig = str(receipt["sig"])
        exp = datetime.fromisoformat(payload["expires_at"])
    except Exception:
        return False, "Recibo malformado"
    if not hmac.compare_digest(_mac(payload), sig):
        return False, "Firma inválida: el contenido fue alterado"
    if exp < (now or datetime.now(timezone.utc)):
        return False, "Recibo vencido"
    if check_nonce and UsedNonce.objects.filter(nonce=payload["nonce"]).exists():
        return False, "Recibo ya usado (nonce repetido)"
    return True, "Firma válida"


def consume(receipt) -> None:
    from .models import UsedNonce
    UsedNonce.objects.create(nonce=receipt["nonce"])
