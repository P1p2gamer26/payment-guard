"""Evalua un endpoint OpenAI-compatible sobre las 25 facturas de data/facturas vs data/extracciones_gold.json.
Uso: python ml/eval.py --base-url http://localhost:8080/v1 [--model x] [--api-key k]
"""
import argparse
import json
import re
import sys
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guard.extractor import PROMPT  # noqa: E402
from guard.data import load_policy  # noqa: E402
from guard.domain import Extraction  # noqa: E402
from guard.engine import find_beneficiary  # noqa: E402

FIELDS = ("monto+moneda", "beneficiario", "benef_resuelto", "cuenta", "fecha")


def norm_name(s):
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", s or "")).strip().lower()


def dec(x):
    try:
        return Decimal(str(x))
    except Exception:
        return None


def ask(base, model, key, text):
    body = {"model": model, "temperature": 0, "stream": False, "messages": [
        {"role": "system", "content": PROMPT}, {"role": "user", "content": f"<<<FACTURA\n{text[:8000]}\nFACTURA>>>"}]}
    h = {"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(), h, method="POST")
    out = json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["message"]["content"].strip()
    out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out)
    return json.loads(out)


POLICY = load_policy()


def _resolved(p):
    try:
        x = Extraction.from_dict({**p, "invoice_id": "eval", "amount": p.get("amount") or "0", "currency": p.get("currency") or "",
                                  "beneficiary_id": None})
        b = find_beneficiary(x, POLICY)
        return b and b["id"]
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", default="payment-guard")
    ap.add_argument("--api-key", default="")
    a = ap.parse_args()
    gold = {g["invoice_id"]: g for g in json.loads((ROOT / "data" / "extracciones_gold.json").read_text(encoding="utf-8"))}
    files = {p.stem: p for p in (ROOT / "data" / "facturas").iterdir()}
    tot = dict.fromkeys(FIELDS, 0)
    print(f"{'id':<4}" + "".join(f"{f:<14}" for f in FIELDS))
    for i, g in sorted(gold.items()):
        try:
            p = ask(a.base_url, a.model, a.api_key, files[i].read_text(encoding="utf-8"))
        except Exception as e:
            p = {}
            print(f"{i}: error {type(e).__name__}: {e}")
        pn, gn = norm_name(p.get("beneficiary_name")), norm_name(g["beneficiary_name"])
        ok = {
            "monto+moneda": dec(p.get("amount")) == dec(g["amount"]) and str(p.get("currency", "")).upper() == g["currency"],
            "beneficiario": bool(pn) and (pn == gn or pn in gn or gn in pn),
            # lo que decide: ¿el motor identifica la ficha correcta del registro maestro con esta lectura?
            "benef_resuelto": _resolved(p) == g["beneficiary_id"],
            "cuenta": str(p.get("bank_account") or "").strip() == g["bank_account"],
            "fecha": p.get("issue_date") == g["issue_date"],
        }
        for f in FIELDS:
            tot[f] += ok[f]
        print(f"{i:<4}" + "".join(f"{'OK' if ok[f] else 'X':<14}" for f in FIELDS))
    n = len(gold)
    print("-" * 60)
    for f in FIELDS:
        print(f"{f:<14}{tot[f]}/{n} = {100 * tot[f] / n:.0f}%")
    print(f"TOTAL        {100 * sum(tot.values()) / (n * len(FIELDS)):.0f}%")


if __name__ == "__main__":
    main()
