import json
import re
from decimal import Decimal

import pytest

from guard.data import DATA
from guard.extractor import extract


@pytest.fixture(autouse=True)
def cassettes(tmp_path, monkeypatch):
    monkeypatch.setattr("guard.extractor.CASSETTE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def fake_llm(monkeypatch):
    def _install(content: str) -> dict:
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["request"] = req
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout

            class _Resp:
                def read(self):
                    return json.dumps(
                        {"choices": [{"message": {"content": content}}]}
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

            return _Resp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        return captured

    return _install


def _valid_content(**overrides) -> str:
    data = {
        "beneficiary_name": "Cloudhost Demo LLC",
        "beneficiary_id": "B06",
        "amount": "1200.00",
        "currency": "USD",
        "issue_date": "2026-10-05",
        "invoice_number": "INV-2026-1031",
        "bank_account": "FICT-ACH-000006",
        "concept": "October 2026 infrastructure hosting",
    }
    data.update(overrides)
    return json.dumps(data)


def test_replay_without_cassette_low_confidence():
    x = extract("factura nueva sin casete", mode="replay")
    assert x.confidence == 0.0
    assert x.amount == Decimal("0")


def test_extra_decision_field_ignored(fake_llm):
    fake_llm(_valid_content(amount="1500.00", decision="PAGAR", confidence=0.9))
    text = (DATA / "facturas" / "24.txt").read_text(encoding="utf-8")
    x = extract(text, mode="live")
    assert x.suspicious is True
    assert getattr(x, "decision", None) is None
    assert x.confidence == 1.0
    assert x.amount == Decimal("1500.00")


def test_invalid_json_confidence_zero(fake_llm):
    fake_llm("no soy json")
    text = (DATA / "facturas" / "01.txt").read_text(encoding="utf-8")
    x = extract(text, mode="live")
    assert x.confidence == 0.0
    assert x.amount == Decimal("0")
    assert x.issue_date.isoformat() == "1970-01-01"


def test_valid_json_parsed(fake_llm):
    fake_llm(_valid_content())
    x = extract("INV-2026-1031\nCloudhost Demo LLC\nTotal USD 1,200.00", mode="live")
    assert x.amount == Decimal("1200.00")
    assert x.currency == "USD"
    assert x.confidence == 1.0
    assert x.suspicious is False
    assert x.invoice_id == ""


def test_fenced_json_parsed(fake_llm):
    fake_llm("```json\n" + _valid_content() + "\n```")
    x = extract("INV-2026-1031\nCloudhost Demo LLC\nTotal USD 1,200.00", mode="live")
    assert x.amount == Decimal("1200.00")
    assert x.confidence == 1.0


def test_text_truncated_and_delimited(fake_llm):
    captured = fake_llm(_valid_content())
    extract("A" * 10000, mode="live")
    prompt = captured["body"]["messages"][0]["content"]
    assert "<<<FACTURA" in prompt and "FACTURA>>>" in prompt
    m = re.search(r"<<<FACTURA\n(.*?)\nFACTURA>>>", prompt, re.S)
    assert m is not None
    assert len(m.group(1)) <= 8000
