from copy import deepcopy

import pytest

from guard.data import load_expected, load_policy
from guard.models import DecisionRecord
from guard.services import process_all, save_policy


@pytest.mark.django_db
def test_process_all_matches_expected():
    recs = process_all(save_policy(load_policy().raw))
    assert {r.invoice.invoice_id: r.outcome for r in recs} == load_expected()
    assert all(r.explanation for r in recs)


@pytest.mark.django_db
def test_new_policy_version_keeps_old():
    v1 = save_policy(load_policy().raw)
    process_all(v1)
    raw = deepcopy(v1.raw)
    raw["reglas_pago"]["umbral_aprobacion_humana_usd"] = 2000
    v2 = save_policy(raw)
    process_all(v2)
    assert DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=v1).outcome == "PAGAR"
    assert DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=v2).outcome == "ESCALAR"


@pytest.mark.django_db
def test_explain_limit_mentions_amounts():
    recs = process_all(save_policy(load_policy().raw))
    exp = next(r for r in recs if r.invoice.invoice_id == "20").explanation
    assert "7,000" in exp and "6,000" in exp


@pytest.mark.django_db
def test_process_text_detects_duplicate_of_paid():
    from guard.data import DATA
    from guard.services import process_text
    process_all(save_policy(load_policy().raw))
    d = process_text((DATA / "facturas" / "02.txt").read_text(encoding="utf-8"), "api-1")
    assert (d.outcome, d.rule) == ("FRENAR", "R_DUPLICADO")
