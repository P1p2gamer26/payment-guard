# ponytail: regex propia estilo invoice2data; usar invoice2data si llegan PDFs reales.
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Optional


def _normalize_number_text(text: str) -> Optional[str]:
    """Try to normalize various number formats to a Decimal-parsable form."""
    t = re.sub(r"\s+", "", text.strip())
    # Check for ambiguous patterns
    if re.search(r"\bor\b", t, re.IGNORECASE) or re.search(r"/", t):
        return None
    if re.search(r"o(?=\d)", t):
        return None

    # US style: 1,200.00
    us_thousand_dot_dec = re.match(r"^-?(\d{1,3}(?:,\d{3})+)\.(\d{2})$", t)
    if us_thousand_dot_dec:
        num = us_thousand_dot_dec.group(1).replace(",", "") + "." + us_thousand_dot_dec.group(2)
        return num

    # European style: 1.250,00
    euro_dot_thousand_comma_dec = re.match(r"^-?(\d{1,3}(?:\.\d{3})+),(\d{2})$", t)
    if euro_dot_thousand_comma_dec:
        num = euro_dot_thousand_comma_dec.group(1).replace(".", "") + "." + euro_dot_thousand_comma_dec.group(2)
        return num

    # COP style with dots as thousand separators, no decimal comma shown (e.g., 8.800.000)
    cop_like = re.match(r"^-?\d{1,3}(?:\.\d{3}){2,}$", t)
    if cop_like:
        return t.replace(".", "")
    cop_like2 = re.match(r"^-?\d{1,3}(?:\.\d{3})+$", t)
    if cop_like2 and not re.search(r",\d{2}$", t):
        return t.replace(".", "")

    # Simple cases
    simple_comma_dec = re.match(r"^-?(\d+),(\d{2})$", t)
    if simple_comma_dec:
        return simple_comma_dec.group(1) + "." + simple_comma_dec.group(2)

    simple_dot_dec = re.match(r"^-?(\d+)\.(\d{2})$", t)
    if simple_dot_dec:
        return simple_dot_dec.group(1) + "." + simple_dot_dec.group(2)

    if re.match(r"^-?\d+$", t):
        return t

    return None


def read_total(text: str) -> Optional[tuple[Decimal, str]]:
    """
    Extract total amount and currency (USD|COP|MXN|EUR) from invoice text.
    - If text is JSON (CFDI), use fields 'total' and 'moneda'.
    - Supports '1,200.00' (US), '8.800.000' (puntos de miles COP), '1.250,00' (coma decimal), '$1,800.00' with USD nearby, 'COP 6.000.000'.
    - Prefer lines with Total/TOTAL/Valor/Amount.
    - If multiple distinct candidates and none clearly the total -> None.
    - Ambiguous format -> None.
    - Returns (Decimal, currency) or None. Never float.
    """
    if not text:
        return None

    stripped = text.strip()
    # Check if JSON
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            total_val = data.get("total")
            moneda = data.get("moneda") or data.get("currency")
            if total_val is None or moneda is None:
                return None
            try:
                d = Decimal(str(total_val))
                return (d, str(moneda).upper())
            except Exception:
                return None
        except json.JSONDecodeError:
            pass

    candidates = []
    lines = text.splitlines()

    for i, line in enumerate(lines):
        line_lower = line.lower()
        priority = 1
        if re.search(r'\btotal\b|TOTAL|total a pagar|grand total|importe total', line_lower):
            priority = 10
        elif re.search(r'\bvalor\b|amount|importe', line_lower):
            priority = 5
        elif re.search(r'subtotal|iva|tax|tasa|descuento', line_lower):
            priority = -5

        # Currency before amount
        for m in re.finditer(r'(?:(USD|COP|MXN|EUR))\s*\$?\s*([0-9][0-9.,]+)', line, re.IGNORECASE):
            amt_raw = m.group(2)
            curr = m.group(1).upper()
            norm = _normalize_number_text(amt_raw)
            if norm:
                try:
                    d = Decimal(norm)
                    if d >= 0:
                        candidates.append((d, curr, priority, i))
                except Exception:
                    pass

        # Amount before currency
        for m in re.finditer(r'\$?\s*([0-9][0-9.,]+)\s*(USD|COP|MXN|EUR)\b', line, re.IGNORECASE):
            amt_raw = m.group(1)
            curr = m.group(2).upper()
            norm = _normalize_number_text(amt_raw)
            if norm:
                try:
                    d = Decimal(norm)
                    if d >= 0:
                        candidates.append((d, curr, priority, i))
                except Exception:
                    pass

        # Dollar sign amounts
        if '$' in line:
            for m in re.finditer(r'\$\s*([0-9][0-9.,]+)', line):
                amt_raw = m.group(1)
                if re.search(r'\bMXN\b', line, re.IGNORECASE):
                    curr = 'MXN'
                elif re.search(r'\bCOP\b', line, re.IGNORECASE):
                    curr = 'COP'
                elif re.search(r'\bEUR\b', line, re.IGNORECASE):
                    curr = 'EUR'
                else:
                    curr = 'USD'
                norm = _normalize_number_text(amt_raw)
                if norm:
                    try:
                        d = Decimal(norm)
                        if d >= 0:
                            candidates.append((d, curr, priority, i))
                    except Exception:
                        pass

    if not candidates:
        return None

    high_priority = [c for c in candidates if c[2] >= 5]
    if high_priority:
        candidates_filtered = high_priority
    else:
        candidates_filtered = candidates

    unique = set((c[0], c[1]) for c in candidates_filtered)
    if len(unique) > 1:
        return None

    result = candidates_filtered[0]
    return (result[0], result[1])
