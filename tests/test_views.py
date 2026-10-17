import json
from pathlib import Path

import pytest

from guard.models import Approval, DecisionRecord, Invoice


@pytest.fixture
def c(client, db):
    client.get("/")  # procesa la política dorada
    return client


def test_board_shows_counts(c):
    html = c.get("/").content.decode()
    assert "Pagos indebidos: 0" in html
    recs = DecisionRecord.objects.all()
    assert [recs.filter(outcome=o).count() for o in ("PAGAR", "FRENAR", "ESCALAR")] == [14, 6, 5]


def test_csv_export_has_25_rows(c):
    r = c.get("/registro/?format=csv")
    assert r["Content-Type"].startswith("text/csv")
    assert len(r.content.decode().strip().splitlines()) == 26


def test_json_export_has_25_with_evidence(c):
    r = c.get("/registro/?format=json")
    assert r["Content-Type"].startswith("application/json")
    data = json.loads(r.content.decode())
    assert len(data) == 25
    for item in data:
        assert {"rule", "outcome", "evidence"} <= set(item)
        assert item["evidence"] and "amount" in item["evidence"]
    # al menos la factura 25 tiene línea de evidencia para el monto
    f25 = next(i for i in data if i["invoice_id"] == "25")
    assert isinstance(f25["evidence"]["amount"], int)
    assert f25["approval"]["requested_by"] and f25["policy_version"] >= 1


def test_detail_shows_master_account_label(c):
    html = c.get("/factura/25/").content.decode()
    assert "registro maestro" in html
    assert "000-FICT-9999" in html
    assert "La factura pedía:" in html


def test_invoice_text_is_escaped(c):
    inv = Invoice.objects.get(invoice_id="24")
    inv.text = "<script>alert(1)</script>"; inv.save()
    html = c.get("/factura/24/").content.decode()
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html


def test_rules_edit_reprocesses(c):
    c.post("/reglas/", {"limite_por_pago": "6000", "umbral_aprobacion": "2000",
                        "monedas": "USD,COP,MXN", "tolerancia": "1"})
    latest = DecisionRecord.objects.order_by("-policy_version__version").first().policy_version
    assert DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=latest).outcome == "ESCALAR"


def test_approve_flow_and_budget_error(c):
    r25 = DecisionRecord.objects.get(invoice__invoice_id="25")
    c.post(f"/aprobaciones/{r25.id}/", {"approver": "cfo@lumbre.example", "note": "verificado", "action": "aprobar"})
    assert Approval.objects.filter(decision=r25, outcome="APROBADO").exists()
    assert "draft_not_executed" in c.get("/factura/25/").content.decode()
    r19 = DecisionRecord.objects.get(invoice__invoice_id="19")
    html = c.post(f"/aprobaciones/{r19.id}/", {"approver": "cfo", "note": "ok", "action": "aprobar"}, follow=True).content.decode()
    assert "presupuesto" in html and not Approval.objects.filter(decision=r19).exists()


def test_api_injection_escalates(c):
    text = Path("data/facturas/24.txt").read_text(encoding="utf-8")
    r = c.post("/api/evaluate", json.dumps({"text": text}), content_type="application/json")
    assert r.status_code == 200 and r.json()["outcome"] == "ESCALAR"


def test_api_rejects_big_body_and_bad_json(c):
    assert c.post("/api/evaluate", json.dumps({"text": "x" * 30000}), content_type="application/json").status_code == 413
    assert c.post("/api/evaluate", "no json", content_type="application/json").status_code == 400
