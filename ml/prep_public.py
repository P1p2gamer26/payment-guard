"""Convierte facturas sinteticas publicas (katanaml invoices, Faker, MIT) al mismo JSON -> ml/train_public.jsonl.
Texto OCR via mychen76/invoices-and-receipts_ocr_v1 (derivado de katanaml). Uso: python ml/prep_public.py [N=640]
"""
import ast
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guard.extractor import PROMPT  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 640
URL = ("https://datasets-server.huggingface.co/rows?dataset=mychen76/invoices-and-receipts_ocr_v1"
       "&config=default&split=train&offset={}&length=100")


def amount(s):
    s = re.sub(r"[^\d,.]", "", s.replace(" ", "")).replace(",", ".")
    return f"{float(s):.2f}"


def convert(row):
    gt = ast.literal_eval(json.loads(row["parsed_data"])["json"])
    h, tot = gt["header"], gt["summary"]["total_gross_worth"]
    if "$" not in tot or not h.get("iban"):
        return None
    name = " ".join(re.split(r"\s+(?=\S*\d)", h["seller"] + " ", maxsplit=1)[0].split())  # corta antes de la direccion
    d = datetime.strptime(h["invoice_date"], "%m/%d/%Y").date().isoformat()
    text = "\n".join(ast.literal_eval(json.loads(row["raw_data"])["ocr_words"]))
    if len(text) > 2500 or not name:
        return None
    concept = gt["items"][0]["item_desc"][:60] if gt["items"] else None
    gold = {"beneficiary_name": name, "beneficiary_id": None, "amount": amount(tot), "currency": "USD", "issue_date": d,
            "invoice_number": h["invoice_no"], "bank_account": h["iban"], "concept": concept}
    return text, gold


def main():
    out, off = [], 0
    while len(out) < N and off < 2000:
        for _ in range(4):  # el servidor de datasets a veces tarda
            try:
                rows = json.load(urllib.request.urlopen(URL.format(off), timeout=120))["rows"]
                break
            except Exception:
                rows = []
        off += 100
        for r in rows:
            try:
                c = convert(r["row"])
            except Exception:
                continue
            if c and len(out) < N:
                out.append({"messages": [{"role": "system", "content": PROMPT},
                                         {"role": "user", "content": f"<<<FACTURA\n{c[0]}\nFACTURA>>>"},
                                         {"role": "assistant", "content": json.dumps(c[1], ensure_ascii=False)}]})
    (ROOT / "ml" / "train_public.jsonl").write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n", encoding="utf-8")
    print(len(out))
    # mezcla: train.jsonl = sinteticas LatAm + publicas, barajadas (seed fija)
    import random
    lines = [l for f in ("train_synth.jsonl", "train_public.jsonl") for l in (ROOT / "ml" / f).read_text(encoding="utf-8").splitlines()]
    random.Random(30).shuffle(lines)
    (ROOT / "ml" / "train.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("train.jsonl:", len(lines))


if __name__ == "__main__":
    main()
