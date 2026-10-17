# Payment Guard — reglas del repo
Plan: PLAN.md. Estrategia: reto Blinka, Hackathon 30X.
- Decisiones solo `PAGAR | FRENAR | ESCALAR`. El LLM extrae, nunca decide. Ante error/duda → ESCALAR.
- Cuenta y beneficiario salen de `data/reglas.json`, nunca de la factura.
- Montos con `Decimal`, nunca float.
- NO editar `verify.sh`, `tests/test_golden.py`, `data/esperado.json`, `data/extracciones_gold.json`.
- Sin secretos en el repo. `DECISION_MODE` default `replay`.
- UI en español; sin `|safe`/`mark_safe` con datos de facturas.
- Atajos deliberados con `# ponytail:`.
- Verificar con `./verify.sh`.
