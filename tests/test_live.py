"""
Tests para: Event logging, /api/eventos, /demo/en-vivo/, /demo/en-vivo/siguiente/,
y aprobación que emite Event aprobacion.
"""
import json

import pytest
from django.test import Client

from guard.data import load_expected, load_policy
from guard.models import DecisionRecord, Event
from guard.services import current_policy, process_all, save_policy


# ---------------------------------------------------------------------------
# 1. process_all emite 25 eventos decision
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_process_all_emite_25_decision():
    pv = save_policy(load_policy().raw)
    Event.objects.all().delete()
    process_all(pv)
    decisions = Event.objects.filter(kind="decision")
    assert decisions.count() == 25


# ---------------------------------------------------------------------------
# 2. /api/eventos devuelve kpis con pagar=14
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_api_eventos_kpis_pagar():
    pv = save_policy(load_policy().raw)
    process_all(pv)
    c = Client()
    resp = c.get("/api/eventos")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert "kpis" in data
    assert data["kpis"]["pagar"] == 14


# ---------------------------------------------------------------------------
# 3. /demo/en-vivo/ + 25 POST siguiente -> coherente, luego done=True
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_demo_en_vivo_siguiente_25_pasos():
    from guard.models import Invoice
    from guard.services import load_invoices

    # partir desde cero: política sin facturas decididas
    pv = save_policy(load_policy().raw)
    load_invoices()  # asegura que las 25 facturas existan en DB

    c = Client()

    # POST /demo/en-vivo/ guarda la política sin procesar
    resp = c.post("/demo/en-vivo/")
    # debe redirigir a /
    assert resp.status_code in (301, 302)

    # obtener la política actual (la que guardó demo_en_vivo)
    from guard.services import current_policy as cp
    pv2 = cp()
    assert pv2.version >= pv.version

    # Hacer 25 siguientes
    done_at = None
    event_25 = None
    for i in range(1, 26):
        resp = c.post("/demo/en-vivo/siguiente/")
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "done" in data
        assert "event" in data
        if i < 25:
            # las primeras 24 deben tener event
            assert data["event"] is not None, f"Paso {i}: se esperaba event no None"
        if i == 25:
            event_25 = data
            done_at = i

    # La 25ª respuesta debe ser coherente: done puede ser True o False
    # pero si done=False hay una factura 25 más. En nuestro caso 25 facturas totales
    # así que la 25ª POST debe tener done=True (ya no quedan más).
    assert event_25 is not None
    assert event_25["done"] is True

    # Hay exactamente 25 DecisionRecord en la nueva política
    assert DecisionRecord.objects.filter(policy_version=pv2).count() == 25

    # Los resultados coinciden con load_expected()
    esperado = load_expected()
    for rec in DecisionRecord.objects.filter(policy_version=pv2).select_related("invoice"):
        assert rec.outcome == esperado[rec.invoice.invoice_id], (
            f"Factura {rec.invoice.invoice_id}: esperado {esperado[rec.invoice.invoice_id]}, "
            f"got {rec.outcome}"
        )


# ---------------------------------------------------------------------------
# 4. Aprobar la factura 25 emite Event aprobacion
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_aprobar_factura_25_emite_event_aprobacion():
    from guard.approval import approve
    from guard.services import load_invoices

    pv = save_policy(load_policy().raw)
    load_invoices()
    process_all(pv)

    rec = DecisionRecord.objects.get(invoice__invoice_id="25", policy_version=pv)
    assert rec.outcome == "ESCALAR"

    # contar eventos de aprobacion antes
    antes = Event.objects.filter(kind="aprobacion").count()

    approve(rec, approver="cfo@lumbre.example", note="ok demo test")

    # debe haber un nuevo evento de aprobacion
    despues = Event.objects.filter(kind="aprobacion").count()
    assert despues == antes + 1

    ev = Event.objects.filter(kind="aprobacion", invoice_id="25").last()
    assert ev is not None
    assert ev.outcome == "APROBADO"
