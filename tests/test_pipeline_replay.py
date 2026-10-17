import dataclasses
from pathlib import Path

from guard.data import DATA, load_expected, load_policy
from guard.engine import find_beneficiary, run_batch
from guard.extractor import extract


def test_replay_llm_matches_expected():
    """Casetes grabados del LLM real (sonnet-4.6 vía 9Router) + motor = 25/25."""
    p = load_policy(); xs = []
    for f in sorted((DATA / "facturas").iterdir()):
        x = extract(f.read_text(encoding="utf-8"), "replay")
        b = find_beneficiary(x, p)
        xs.append(dataclasses.replace(x, invoice_id=Path(f).stem, beneficiary_id=b and b["id"]))
    assert {d.invoice_id: d.outcome for d in run_batch(xs, p)} == load_expected()
