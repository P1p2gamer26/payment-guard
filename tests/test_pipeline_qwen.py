import dataclasses

from guard import extractor
from guard.data import DATA, load_expected, load_policy
from guard.engine import Ledger, allowed_to_pay, decide, find_beneficiary
from guard.second_read import read_total


def test_own_model_readings_decide_25_of_25(monkeypatch):
    """Lecturas grabadas del modelo propio (Qwen2.5-1.5B afinado) + motor = 25/25, 0 indebidos."""
    monkeypatch.setattr(extractor, "CASSETTE_DIR", DATA.parent / "cassettes_qwen")
    p = load_policy(); ledger = Ledger(p.period_budget_remaining_usd, []); got = {}
    for f in sorted((DATA / "facturas").iterdir()):
        text = f.read_text(encoding="utf-8")
        x = extractor.extract(text, "replay")
        b = find_beneficiary(x, p)
        x = dataclasses.replace(x, invoice_id=f.stem, beneficiary_id=b and b["id"])
        d = decide(x, p, ledger, second_read=read_total(text))
        if d.outcome == "PAGAR":
            assert allowed_to_pay(x, p, ledger), f.stem
            ledger.remaining_usd -= d.amount_usd; ledger.paid.append(x)
        got[f.stem] = d.outcome
    assert got == load_expected()
