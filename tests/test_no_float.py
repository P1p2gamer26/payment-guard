"""Ningún float en la ruta del dinero: montos siempre Decimal. Excepción explícita con '# float-ok'."""
import ast
from pathlib import Path

FILES = ["guard/engine.py", "guard/approval.py", "guard/receipt.py", "guard/services.py", "guard/domain.py"]


def test_no_float_in_money_path():
    bad = []
    for f in FILES:
        src = Path(f).read_text(encoding="utf-8")
        lines = src.splitlines()
        for n in ast.walk(ast.parse(src)):
            hit = (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "float") or \
                  (isinstance(n, ast.Constant) and isinstance(n.value, float))
            if hit and "float-ok" not in lines[n.lineno - 1]:
                bad.append(f"{f}:{n.lineno}: {lines[n.lineno - 1].strip()}")
    assert not bad, "float en ruta de dinero:\n" + "\n".join(bad)
