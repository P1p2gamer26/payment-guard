from datetime import datetime, timedelta, timezone

import pytest

from guard import receipt as rcpt
from guard.approval import approve
from guard.data import load_policy
from guard.models import Approval, DecisionRecord, UsedNonce
from guard.services import process_all, save_policy


@pytest.fixture
def processed(db):
    return process_all(save_policy(load_policy().raw))


def rec(i):
    return DecisionRecord.objects.get(invoice__invoice_id=i)


def test_valid_signature(processed):
    assert rcpt.verify(rec("25").receipt) == (True, "Firma válida")


def test_altered_amount_invalid(processed):
    r = {**rec("25").receipt, "amount": "1"}
    ok, motivo = rcpt.verify(r)
    assert not ok and "Firma inválida" in motivo


def test_expired(processed):
    ok, motivo = rcpt.verify(rec("25").receipt, now=datetime.now(timezone.utc) + timedelta(hours=25))
    assert not ok and "vencido" in motivo


def test_nonce_reuse(processed):
    r = rec("25").receipt
    rcpt.consume(r)
    ok, motivo = rcpt.verify(r)
    assert not ok and "nonce" in motivo
    assert rcpt.verify(r, check_nonce=False)[0]


def test_approve_altered_receipt_creates_no_draft(processed):
    r = rec("25")
    with pytest.raises(ValueError, match="el monto no coincide con lo decidido"):
        approve(r, "cfo", "ok", receipt={**r.receipt, "amount": "1"})
    assert not Approval.objects.exists() and not UsedNonce.objects.exists()


def test_approve_marks_nonce_and_signs_draft(processed):
    r = rec("25")
    d = approve(r, "cfo", "verificado")
    assert d["receipt_sig"] == r.receipt["sig"]
    assert UsedNonce.objects.filter(nonce=r.receipt["nonce"]).exists()


def test_tamper_view_shows_red_stamp(client, processed):
    html = client.post("/factura/25/alterar/", {"monto": "1"}).content.decode()
    assert "Firma inválida: el monto no coincide con lo decidido" in html
    assert not Approval.objects.exists()
    assert "Firma válida" in client.get("/factura/25/").content.decode()
