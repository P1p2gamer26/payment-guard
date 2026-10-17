from copy import deepcopy
from decimal import Decimal

import pytest

from guard import receipt as rcpt
from guard.approval import approve
from guard.data import load_policy
from guard.models import DecisionRecord, ExtractionCorrection, Invoice
from guard.services import correct_field, process_all, save_policy


@pytest.fixture
def pv(db):
    return process_all(save_policy(load_policy().raw))[0].policy_version


@pytest.fixture
def c(client, db):
    client.get("/")  # procesa la política dorada
    return client


def test_corregir_monto_06_pasa_a_escalar(pv):
    rec = DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=pv)
    assert rec.outcome == "PAGAR"
    rec = correct_field("06", "amount", "3500", "cfo@lumbre.example", "Monto real acordado con el cliente")
    assert rec.outcome == "ESCALAR"
    assert rec.rule in ("R_UMBRAL", "R_CONTRATO")
    assert rec.amount_usd == Decimal("3500").quantize(Decimal("0.01"))
    cor = ExtractionCorrection.objects.get(invoice__invoice_id="06")
    assert cor.field == "amount"
    assert Decimal(cor.old_value) == Decimal("2500.00")
    assert Decimal(cor.new_value) == Decimal("3500")
    assert cor.actor == "cfo@lumbre.example"
    assert cor.reason
    inv = Invoice.objects.get(invoice_id="06")
    assert Decimal(str(inv.extraction["amount"])) == Decimal("3500")


def test_corregir_cuenta_bancaria_no_permitido(pv):
    with pytest.raises(ValueError):
        correct_field("06", "bank_account", "000-FICT-9999", "cfo@lumbre.example", "cuenta nueva")
    with pytest.raises(ValueError):
        correct_field("06", "beneficiary_id", "B01", "cfo@lumbre.example", "otro beneficiario")
    assert not ExtractionCorrection.objects.exists()


def test_corregir_sin_motivo_es_error(pv):
    with pytest.raises(ValueError):
        correct_field("06", "amount", "3500", "cfo@lumbre.example", "   ")
    with pytest.raises(ValueError):
        correct_field("06", "amount", "0", "cfo@lumbre.example", "monto invalido")
    with pytest.raises(ValueError):
        correct_field("06", "currency", "pesos", "cfo@lumbre.example", "moneda rara")
    assert not ExtractionCorrection.objects.exists()
    assert DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=pv).outcome == "PAGAR"


def test_recibo_anterior_deja_de_verificar(pv):
    rec = DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=pv)
    viejo = deepcopy(rec.receipt)
    assert rcpt.verify(viejo, check_nonce=False)[0]
    correct_field("06", "amount", "3500", "cfo@lumbre.example", "Monto real")
    rec.refresh_from_db()
    ok, motivo = rcpt.verify(viejo)
    assert not ok and "ya" in motivo  # su nonce quedó quemado: nunca más sirve para aprobar
    assert rec.receipt["nonce"] != viejo["nonce"]
    assert rcpt.verify(rec.receipt)[0]
    assert viejo["amount"] != str(Invoice.objects.get(invoice_id="06").extraction["amount"])


def test_no_se_corrige_si_ya_fue_decidida_por_una_persona(pv):
    rec = DecisionRecord.objects.get(invoice__invoice_id="25", policy_version=pv)
    approve(rec, "cfo@lumbre.example", "verificado por canal alternativo")
    with pytest.raises(ValueError) as e:
        correct_field("25", "amount", "1900000", "ap@lumbre.example", "otro monto")
    assert str(e.value) == "ya fue decidida por una persona"


def test_vista_correccion_aplica_y_muestra_historial(c):
    html = c.get("/factura/06/").content.decode()
    assert 'action="/factura/06/corregir/"' in html
    r = c.post("/factura/06/corregir/", {"campo": "amount", "valor": "3500",
                                         "motivo": "Monto real acordado"}, follow=True)
    assert r.status_code == 200
    body = r.content.decode()
    assert "ESCALAR" in body and "Historial de correcciones" in body
    assert "Monto real acordado" in body
    assert DecisionRecord.objects.get(invoice__invoice_id="06").outcome == "ESCALAR"
    assert ExtractionCorrection.objects.filter(invoice__invoice_id="06", field="amount").count() == 1


def test_vista_correccion_con_motivo_vacio_muestra_error(c):
    r = c.post("/factura/06/corregir/", {"campo": "amount", "valor": "3500", "motivo": ""}, follow=True)
    assert "el motivo de la corrección es obligatorio." in r.content.decode()
    assert not ExtractionCorrection.objects.exists()
    assert DecisionRecord.objects.get(invoice__invoice_id="06").outcome == "PAGAR"
