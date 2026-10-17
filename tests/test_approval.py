import pytest

from guard.approval import approve, reject
from guard.data import load_policy
from guard.models import DecisionRecord
from guard.services import process_all, save_policy


@pytest.fixture
def processed(db):
    return process_all(save_policy(load_policy().raw))


def rec(i):
    return DecisionRecord.objects.get(invoice__invoice_id=i)


def test_approve_25_pays_master_account_not_new_one(processed):
    d = approve(rec("25"), "cfo@lumbre.example", "verificado por teléfono con Ingrid")
    assert d["status"] == "draft_not_executed"
    assert d["beneficiary_account"] == "000-FICT-0019"  # nunca la 9999 de la factura
    assert (d["amount_minor"], d["currency"], d["rail"]) == (200000000, "COP", "BRE_B")


def test_approve_rechecks_budget(processed):
    with pytest.raises(ValueError, match="presupuesto"):
        approve(rec("19"), "cfo@lumbre.example", "ok")


def test_approve_new_beneficiary_needs_registration(processed):
    with pytest.raises(ValueError, match="beneficiario"):
        approve(rec("17"), "cfo@lumbre.example", "ok")


def test_note_required_and_only_once(processed):
    with pytest.raises(ValueError):
        approve(rec("24"), "cfo@lumbre.example", "  ")
    reject(rec("24"), "cfo@lumbre.example", "inyección: confirmar con Delta Pixel")
    with pytest.raises(ValueError):
        approve(rec("24"), "cfo@lumbre.example", "ok")


def test_cannot_approve_pagar_or_frenar(processed):
    for i in ("01", "20"):
        with pytest.raises(ValueError):
            approve(rec(i), "cfo@lumbre.example", "ok")
