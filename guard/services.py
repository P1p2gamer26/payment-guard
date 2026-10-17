import dataclasses
from decimal import Decimal

from django.conf import settings
from django.db import models

from .data import DATA, load_policy
from .domain import Extraction, Policy
from .engine import Decision, Ledger, decide, find_beneficiary
from .explain import explain
from .models import Approval, DecisionRecord, Invoice, PolicyVersion
from .extractor import extract
from .second_read import read_total

CENT = Decimal("0.01")


def save_policy(raw: dict) -> PolicyVersion:
    last = PolicyVersion.objects.order_by("-version").values_list("version", flat=True).first()
    return PolicyVersion.objects.create(version=(last or 0) + 1, raw=raw)


def current_policy() -> PolicyVersion:
    pv = PolicyVersion.objects.order_by("-version").first()
    if pv is None:
        pv = save_policy(load_policy().raw)
    return pv


def load_invoices() -> list[Invoice]:
    out = []
    for f in sorted((DATA / "facturas").iterdir()):
        text = f.read_text(encoding="utf-8")
        inv, _ = Invoice.objects.get_or_create(
            invoice_id=f.stem, defaults={"filename": f.name, "text": text}
        )
        out.append(inv)
    return out


def _serialize_extraction(x: Extraction) -> dict:
    d = dataclasses.asdict(x)
    d["amount"] = str(d["amount"])
    d["issue_date"] = d["issue_date"].isoformat() if d["issue_date"] else None
    return d


def _serialize_second_read(sr) -> list | None:
    if sr is None:
        return None
    return [str(sr[0]), sr[1]]


def process_all(pv: PolicyVersion) -> list[DecisionRecord]:
    policy = Policy(pv.raw, pv.version)
    ledger = Ledger(policy.period_budget_remaining_usd, [])
    records = []
    for inv in load_invoices():
        x = extract(inv.text, mode=settings.DECISION_MODE)
        b = find_beneficiary(x, policy)
        x = dataclasses.replace(x, invoice_id=inv.invoice_id, beneficiary_id=b and b["id"])
        sr = read_total(inv.text)
        d = decide(x, policy, ledger, second_read=sr)
        if d.outcome == "PAGAR":
            ledger.remaining_usd -= d.amount_usd
            ledger.paid.append(x)
        inv.extraction = _serialize_extraction(x)
        inv.save(update_fields=["extraction"])
        rec, _ = DecisionRecord.objects.update_or_create(
            invoice=inv,
            policy_version=pv,
            defaults={
                "outcome": d.outcome,
                "rule": d.rule,
                "amount_usd": d.amount_usd,
                "facts": d.facts,
                "explanation": explain(d, x),
                "second_read": _serialize_second_read(sr),
            },
        )
        records.append(rec)
    records.sort(key=lambda r: r.invoice.invoice_id)
    return records


def spent_usd(pv: PolicyVersion) -> Decimal:
    pagados = DecisionRecord.objects.filter(policy_version=pv, outcome="PAGAR")
    gastado = sum((r.amount_usd for r in pagados if r.amount_usd is not None), Decimal("0"))
    aprobados = Approval.objects.filter(outcome="APROBADO", decision__policy_version=pv)
    gastado += sum(
        (a.decision.amount_usd for a in aprobados if a.decision.amount_usd is not None),
        Decimal("0"),
    )
    return gastado


def process_text(text: str, invoice_id: str) -> Decision:
    pv = current_policy()
    policy = Policy(pv.raw, pv.version)
    # lo ya pagado/aprobado alimenta la detección de duplicados, no solo el presupuesto
    done = DecisionRecord.objects.filter(policy_version=pv).filter(
        models.Q(outcome="PAGAR") | models.Q(approval__outcome="APROBADO")).select_related("invoice")
    paid = [Extraction.from_dict(r.invoice.extraction) for r in done if r.invoice.extraction]
    ledger = Ledger(policy.period_budget_remaining_usd - spent_usd(pv), paid)
    x = extract(text, mode=settings.DECISION_MODE)
    b = find_beneficiary(x, policy)
    x = dataclasses.replace(x, invoice_id=invoice_id, beneficiary_id=b and b["id"])
    return decide(x, policy, ledger, second_read=read_total(text))
