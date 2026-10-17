from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

from guard import engine
from guard.data import load_gold, load_policy
from guard.domain import Policy
from guard.engine import Ledger, decide


def gold(i):
    return next(g for g in load_gold() if g.invoice_id == i)


def fresh(p):
    return Ledger(p.period_budget_remaining_usd, [])


def test_exception_in_rule_escalates(monkeypatch):
    def boom(c):
        raise RuntimeError("x")
    monkeypatch.setattr(engine, "RULES", [boom])
    p = load_policy()
    d = decide(gold("01"), p, fresh(p))
    assert (d.outcome, d.rule) == ("ESCALAR", "R_ERROR")


def test_lower_threshold_escalates_06():
    raw = deepcopy(load_policy().raw)
    raw["reglas_pago"]["umbral_aprobacion_humana_usd"] = 2000
    p = Policy(raw, 2)
    d = decide(gold("06"), p, fresh(p))
    assert (d.outcome, d.rule) == ("ESCALAR", "R_UMBRAL")


def test_limit_frena_20():
    p = load_policy()
    d = decide(gold("20"), p, fresh(p))
    assert (d.outcome, d.rule) == ("FRENAR", "R_LIMITE")
    assert d.facts == {"monto_usd": "7000.06", "limite": "6000"}


def test_misread_amount_escalates():
    p = load_policy()
    x = replace(gold("02"), amount=Decimal("8800"))
    d = decide(x, p, fresh(p), second_read=(Decimal("8800000"), "COP"))
    assert (d.outcome, d.rule) == ("ESCALAR", "R_DOBLE_LECTURA")


def test_unknown_currency_never_pays():
    p = load_policy()
    d = decide(replace(gold("01"), currency="XYZ"), p, fresh(p))
    assert d.outcome != "PAGAR"


def test_non_positive_amount_never_pays():
    from dataclasses import replace
    from decimal import Decimal
    from guard.data import load_gold, load_policy
    from guard.engine import Ledger, decide
    p = load_policy(); g = {x.invoice_id: x for x in load_gold()}
    for amt in (Decimal("0"), Decimal("-1200")):
        d = decide(replace(g["01"], amount=amt), p, Ledger(p.period_budget_remaining_usd, []))
        assert d.outcome == "ESCALAR"


def test_missing_date_uses_reception_date():
    from dataclasses import replace
    from guard.data import load_gold, load_policy
    from guard.engine import Ledger, decide
    p = load_policy(); g = {x.invoice_id: x for x in load_gold()}
    d = decide(replace(g["01"], issue_date=None), p, Ledger(p.period_budget_remaining_usd, []))
    assert d.outcome == "PAGAR"
