from guard import ui
from guard.engine import RULES


def test_reglas_cubren_el_motor():
    assert [r.__name__.upper() for r in RULES] == [r[0] for r in ui.REGLAS if r[0] != "OK"]


def test_evidencia_linea_literal_y_sin_inventar():
    texto = "Hola\nInvoice: INV-1 | Amount: USD 1,200.00 | Due: 2026-10-30\nPay to: Cloudhost Demo LLC"
    ex = {"amount": "1200.00", "currency": "USD", "beneficiary_name": "Cloudhost Demo LLC",
          "concept": "hosting octubre", "invoice_number": "INV-1"}
    _, ev = ui.build_doc(texto, ex)
    assert ev["amount"]["line"] == 2 and ev["amount"]["needle"] == "1,200.00"
    assert ev["beneficiary_name"]["line"] == 3
    assert "concept" not in ev  # no aparece literal: sin evidencia directa
