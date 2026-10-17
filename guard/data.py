import json
from pathlib import Path

from .domain import Extraction, Policy

DATA = Path(__file__).resolve().parent.parent / "data"


def load_policy(path=DATA / "reglas.json") -> Policy:
    return Policy(json.loads(Path(path).read_text(encoding="utf-8")))


def load_gold() -> list[Extraction]:
    rows = json.loads((DATA / "extracciones_gold.json").read_text(encoding="utf-8"))
    return [Extraction.from_dict(r) for r in rows]


def load_expected() -> dict[str, str]:
    rows = json.loads((DATA / "esperado.json").read_text(encoding="utf-8"))
    return {r["id"]: r["decision"] for r in rows}
