from decimal import Decimal

from guard.data import load_expected, load_gold, load_policy


def test_data_consistent():
    gold = load_gold(); exp = load_expected()
    assert len(gold) == 25 and set(exp) == {g.invoice_id for g in gold}
    assert list(exp.values()).count("PAGAR") == 14
    assert exp["17"] == exp["18"] == "ESCALAR"
    assert load_policy().per_payment_limit_usd == Decimal("6000")
