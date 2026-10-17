import copy
from dataclasses import replace
from decimal import Decimal

from guard.data import load_gold, load_policy
from guard.domain import Policy
from guard.engine import Ledger, decide

G = {x.invoice_id: x for x in load_gold()}


def _p(**reglas):
    raw = copy.deepcopy(load_policy().raw)
    raw["reglas_pago"].update(reglas)
    return Policy(raw)


def _usd(amount):  # factura 13 es USD, contrato 950: se fija el contrato al monto para aislar el límite
    x = replace(G["13"], amount=Decimal(amount))
    return x


def _decide(x, p, restante="23000"):
    raw = copy.deepcopy(p.raw)
    for b in raw["beneficiarios_permitidos"]:
        if b["id"] == "B13":
            b["contrato"]["monto"] = float(x.amount)  # float-ok: dato de configuración JSON, no cálculo de dinero
    return decide(x, Policy(raw), Ledger(Decimal(restante), []))


def test_exactly_threshold_pays():
    assert _decide(_usd("3000.00"), _p()).outcome == "PAGAR"


def test_one_cent_over_threshold_escalates():
    d = _decide(_usd("3000.01"), _p())
    assert (d.outcome, d.rule) == ("ESCALAR", "R_UMBRAL")


def test_exactly_limit_is_not_frozen_by_limit():
    d = _decide(_usd("6000.00"), _p(umbral_aprobacion_humana_usd=10000))
    assert d.outcome == "PAGAR"


def test_one_cent_over_limit_freezes():
    d = _decide(_usd("6000.01"), _p(umbral_aprobacion_humana_usd=10000))
    assert (d.outcome, d.rule) == ("FRENAR", "R_LIMITE")


def test_exactly_remaining_budget_pays_and_one_cent_more_freezes():
    assert _decide(_usd("950.00"), _p(), restante="950.00").outcome == "PAGAR"
    d = _decide(_usd("950.00"), _p(), restante="949.99")
    assert (d.outcome, d.rule) == ("FRENAR", "R_PRESUPUESTO")
