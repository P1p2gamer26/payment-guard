import json
from decimal import Decimal
from pathlib import Path

import pytest

from guard.second_read import read_total


@pytest.mark.parametrize("text,expected", [
    ("Total: USD 1,200.00", (Decimal("1200.00"), "USD")),
    ("Valor: COP 8.800.000", (Decimal("8800000"), "COP")),
    ("Total a pagar $ 1.250,00 MXN", (Decimal("1250.00"), "MXN")),
    ("USD 1,250 o 1.250?", None),
])
def test_read_total(text, expected):
    assert read_total(text) == expected


def test_matches_gold_never_wrong():
    gold = {g["invoice_id"]: g for g in json.loads(Path("data/extracciones_gold.json").read_text(encoding="utf-8"))}
    hits = 0
    for f in Path("data/facturas").iterdir():
        r = read_total(f.read_text(encoding="utf-8"))
        if r is None:
            continue
        assert r == (Decimal(gold[f.stem]["amount"]), gold[f.stem]["currency"]), f.stem
        hits += 1
    assert hits >= 20
