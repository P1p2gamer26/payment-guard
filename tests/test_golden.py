# El verificador. No se edita después del Task 1 (ver CLAUDE.md).
from guard.data import load_expected, load_gold, load_policy
from guard.engine import Ledger, allowed_to_pay, decide, run_batch


def test_golden_25():
    decisions = run_batch(load_gold(), load_policy())
    got = {d.invoice_id: d.outcome for d in decisions}
    assert got == load_expected()


def test_every_pagar_passes_oracle():
    p = load_policy(); ledger = Ledger(p.period_budget_remaining_usd, [])
    for x in sorted(load_gold(), key=lambda g: g.invoice_id):
        d = decide(x, p, ledger)
        if d.outcome == "PAGAR":
            assert allowed_to_pay(x, p, ledger)
            ledger.remaining_usd -= d.amount_usd; ledger.paid.append(x)
