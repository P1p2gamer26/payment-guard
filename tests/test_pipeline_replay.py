import dataclasses
from pathlib import Path

from guard.data import DATA, load_expected, load_policy
from guard.engine import Ledger, decide, find_beneficiary
from guard.second_read import read_total
from guard.extractor import extract


def test_replay_llm_matches_expected():
    """Casetes del LLM real (sonnet-4.6 vía 9Router) + doble lectura + motor = 25/25."""
    p = load_policy(); ledger = Ledger(p.period_budget_remaining_usd, []); got = {}
    for f in sorted((DATA / "facturas").iterdir()):
        text = f.read_text(encoding="utf-8")
        x = extract(text, "replay")
        b = find_beneficiary(x, p)
        x = dataclasses.replace(x, invoice_id=Path(f).stem, beneficiary_id=b and b["id"])
        d = decide(x, p, ledger, second_read=read_total(text))
        if d.outcome == "PAGAR":
            ledger.remaining_usd -= d.amount_usd; ledger.paid.append(x)
        got[d.invoice_id] = d.outcome
    assert got == load_expected()
