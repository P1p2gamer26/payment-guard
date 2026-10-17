# Payment Guard

**Demo en vivo:** https://p1p2gamer26.pythonanywhere.com/
**Repo:** https://github.com/P1p2gamer26/payment-guard

Agente que lee facturas de contratistas en LatAm y decide **PAGAR / FRENAR / ESCALAR** con reglas en código, explica cada decisión y pide aprobación humana cuando algo se sale de las reglas. Hackathon 30X, reto Blinka.

- **Problema:** las finanzas de empresas de EE. UU. con contratistas en LatAm revisan a mano decenas de facturas al mes. Nadie delega el pago a un agente porque la barrera es la confianza: no puede probar que respeta las reglas.
- **Idea:** el código decide, el LLM solo lee. El LLM extrae campos; un motor de reglas con *default-deny* decide y cita la regla.
- **Salida:** un borrador de pago en formato Blinka (`draft_not_executed`). No mueve dinero.

## Demo

- App: https://p1p2gamer26.pythonanywhere.com/
- Video (3 min): `URL_VIDEO`

## Resultados

| Qué | Resultado |
|---|---|
| Golden (25 facturas) | **25 / 25** decisiones esperadas (14 PAGAR / 6 FRENAR / 5 ESCALAR), **0** pagos indebidos |
| Arena (415 ataques) — política v1 | **170** pagos indebidos (fraccionamiento 39, cuenta 17, inyección 7, unicode 62, duplicado 40, fecha 5) |
| Arena (415 ataques) — política v2 | **0** pagos indebidos |
| Tests | **69** (pytest) |

Se reproduce con `./verify.sh` (modo `replay`, sin red). El verificador independiente `allowed_to_pay` re-chequea los límites duros sin usar el motor. Doble lectura (regex vs. LLM): coincide en 20/25, se abstiene en 5, **nunca contradice**.

## Cómo funciona

```
texto de la factura (correo / chat / CFDI JSON / cuenta de cobro)
  -> extracción LLM (la factura va como dato, no como instrucción)
  -> segunda lectura por regex (monto y moneda)
  -> motor de reglas default-deny
  -> PAGAR / FRENAR / ESCALAR + regla citada
  -> explicación en lenguaje llano + registro
  -> ESCALAR: aprobación humana que RE-CHEQUEA los límites duros
  -> borrador formato Blinka (draft_not_executed)
```

Detalle y diagramas: [`docs/arquitectura.md`](docs/arquitectura.md).

## Reglas (en orden; la primera que dispara gana)

| # | Regla | Dispara cuando | Resultado |
|---|---|---|---|
| 1 | `R_SOSPECHA` | el texto trae instrucciones para alterar reglas (prompt injection) | ESCALAR |
| 2 | `R_CONFIANZA` | falta monto/moneda/cuenta o el monto es <= 0 | ESCALAR |
| 3 | `R_DOBLE_LECTURA` | el regex lee monto o moneda distintos al LLM | ESCALAR |
| 4 | `R_MONEDA` | moneda fuera de USD/COP/MXN | FRENAR |
| 5 | `R_BENEFICIARIO` | beneficiario no está en el registro maestro (o es ambiguo) | ESCALAR |
| 6 | `R_CUENTA` | la cuenta de la factura difiere de la registrada | ESCALAR |
| 7 | `R_DUPLICADO` | mismo número, concepto o monto+mes que un pago previo | FRENAR |
| 8 | `R_FECHA` | emisión futura o más de 60 días | FRENAR |
| 9 | `R_CONTRATO` | monto difiere del contrato más de 1 % | ESCALAR |
| 10 | `R_LIMITE` | supera el límite duro por pago (USD 6.000) | FRENAR |
| 11 | `R_UMBRAL` | supera el umbral de aprobación humana (USD 3.000) | ESCALAR |
| 12 | `R_PRESUPUESTO` | no alcanza el presupuesto restante del periodo | FRENAR |
| - | `R_ERROR` | cualquier excepción | ESCALAR |
| - | `OK` | ninguna regla dispara | PAGAR |

Criterio: **FRENAR** = inválido sin discusión. **ESCALAR** = una persona puede aprobarlo o hay señal de fraude.

## Los 11 casos trampa

| Factura | Trampa | Decisión | Regla |
|---|---|---|---|
| 15 | Duplicado exacto (mismo número y monto) | FRENAR | `R_DUPLICADO` |
| 16 | Duplicado con otro número | FRENAR | `R_DUPLICADO` |
| 17 | Beneficiario nuevo | ESCALAR | `R_BENEFICIARIO` |
| 18 | Monto no cuadra con el contrato | ESCALAR | `R_CONTRATO` |
| 19 | Sobre el umbral de aprobación (USD 4.000) | ESCALAR | `R_UMBRAL` |
| 20 | Sobre el límite por pago (USD 7.000) | FRENAR | `R_LIMITE` |
| 21 | Presupuesto insuficiente | FRENAR | `R_PRESUPUESTO` |
| 22 | Moneda no permitida (EUR) | FRENAR | `R_MONEDA` |
| 23 | Fecha de emisión futura | FRENAR | `R_FECHA` |
| 24 | Prompt injection oculta | ESCALAR | `R_SOSPECHA` |
| 25 | Cambio de cuenta bancaria con urgencia | ESCALAR | `R_CUENTA` |

## Controles de seguridad

- **Default-deny:** el código decide, el LLM solo extrae. Extracción dudosa, casete ausente o cualquier excepción -> ESCALAR, jamás PAGAR.
- **Doble llave LLM vs. regex:** segunda lectura de monto y moneda por regex; si difieren del LLM -> ESCALAR.
- **Cuenta y beneficiario siempre del registro maestro** (`data/reglas.json`), nunca de la factura. Cambio de cuenta -> ESCALAR.
- **Re-chequeo de límites al aprobar:** `allowed_to_pay` re-valida los límites duros en la aprobación humana (idea de imprest); nadie aprueba lo que la regla prohíbe.
- **Recibo HMAC de un solo uso con vencimiento:** el guardián verifica firma, vencimiento y nonce no usado antes de emitir el borrador.
- **Separación de funciones:** quien solicita (`Invoice.requested_by`) no puede aprobar.
- **Inyección detectada en código, nunca obedecida:** el texto de la factura es dato (`R_SOSPECHA`); un campo `decision` del LLM se descarta.
- **Montos con `Decimal`**, nunca `float`.

## Modelo propio (extractor)

- **Qwen2.5 afinado con LoRA (Unsloth)** en Colab T4 gratis sobre **1.290 ejemplos** (900 sintéticos LatAm + 390 públicos MIT, ver `ml/DATASETS.md`). Las **25 facturas del demo NUNCA se usan para entrenar** (solo evaluación).
- **0.5B:** 162 pasos en ~6 min, loss final **0.042**. **1.5B:** resultados pendientes.
- Servido en **CPU con llama.cpp** en un Hugging Face Space; la demo pública usa **lecturas grabadas (replay)** para no depender de red.
- Cómo reproducir: `ml/gen_synthetic.py`, `ml/prep_public.py`, `ml/finetune_colab.ipynb`, `ml/eval.py`.

## Qué se descartó y por qué

Entradas PDF/foto/XML, notificaciones por Telegram/correo y observabilidad (métricas, trazas): no cambian la decisión ni se ven en un demo de 3 min. El set de demo es texto, chat y CFDI JSON; el valor está en el motor de reglas, no en el pipeline de ingestión.

## Correr local

```bash
python -m venv .venv
pip install -r requirements.txt     # dentro del venv
./verify.sh                         # 25/25 en modo replay
python manage.py migrate
python manage.py runserver
```

`DECISION_MODE`:

| Modo | Qué hace |
|---|---|
| `replay` (defecto) | usa las respuestas grabadas en `cassettes/`; sin red, $0 |
| `record` | llama al LLM y graba la respuesta |
| `live` | llama al LLM sin grabar |

Variables (`.env.example`): `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DECISION_MODE`, `LLM_BASE_URL` (defecto `http://localhost:20128/v1`, 9Router), `LLM_API_KEY`, `LLM_MODEL` (defecto `ag/claude-sonnet-4-6`).

## Costo

~1 llamada LLM por factura (~1k tokens): centavos por factura. En `replay`, $0.

## Alcance honesto

- **El set es sintético:** 25 facturas ficticias de una empresa ficticia. Las cifras (25/25, 0 pagos indebidos) valen para las entradas probadas, no son una garantía general.
- **No mueve dinero:** emite un borrador `draft_not_executed`; no se conecta a ninguna plataforma de pagos.
- **No hace KYC/AML** ni verifica la identidad o sanciones de las empresas.
- **El modelo solo extrae** campos; nunca decide. Si no hay casete o la lectura es dudosa, ESCALA.
- **No cubre:** PDFs/fotos/XML reales (el set son texto, chat y CFDI JSON), colusión de aprobadores, cuentas del registro maestro comprometidas, tipos de cambio en vivo (fijos en `reglas.json`), ni ataques fuera de las categorías de la arena.
- Recibo firmado con HMAC y clave derivada de `SECRET_KEY` (no es PKI): protege contra alteración entre la decisión y la aprobación, no contra quien controle el servidor.

## Arena (pentest automático)

`guard/arena.py` genera ataques a partir de las trampas y corre cada uno por el motor, la segunda lectura y el oráculo `allowed_to_pay`. Un ataque cuenta como **pago indebido** si el motor dice PAGAR y la intención del ataque (o el oráculo) dice que no debía pagarse. Categorías: fraccionamiento, cuenta (variantes de formato), inyección (ES/EN/PT, mayúsculas, letras separadas, invisibles, ancho completo, homoglifos), unicode, duplicado, moneda ambigua, fecha (futura y dd/mm ambigua).

Las defensas nuevas son banderas de la política (`reglas_pago.anti_fraccionamiento`, `reglas_pago.normalizar_unicode`): ausentes en el mandato v1 (`data/reglas.json`), activas en v2.

| Mandato | Ataques | Pagos indebidos |
|---|---|---|
| v1 (base) | 415 | **170** (fraccionamiento 39, cuenta 17, inyección 7, unicode 62, duplicado 40, fecha 5) |
| v2 (`anti_fraccionamiento` + `normalizar_unicode`) | 415 | **0** |

Qué cierra v2: `R_FRACCIONAMIENTO` (suma del beneficiario en el mes, pagos y escaladas pendientes, sobre el umbral o el contrato), `R_UNICODE` (invisibles, ancho completo, cirílico/griego en campos clave), número de factura comparado en forma canónica, cuenta exacta (sin tolerancia de mayúsculas) y detección endurecida de inyecciones y fechas dd/mm ambiguas. El golden sigue 25/25 en v1 y en v2.

```bash
.venv/Scripts/python manage.py arena      # tabla v1 vs v2
.venv/Scripts/python -m pytest -q tests/test_arena.py tests/test_receipt.py
```

En la app: tablero `/` -> «Correr arena»; `/reglas/` -> «Aplicar mandato v2», y volver a correr la arena.

## Dónde se garantiza cada control

| Control | Código | Test | Cómo verlo en la demo |
|---|---|---|---|
| Default-deny: guard/engine.py decide() (excepción -> ESCALAR R_ERROR) | guard/engine.py decide() (excepción -> ESCALAR R_ERROR) | tests/test_engine.py::test_exception_in_rule_escalates | cualquier factura rara termina en ESCALAR |
| Doble llave LLM vs regex: guard/engine.py r_doble_lectura + guard/second_read.py | guard/engine.py r_doble_lectura + guard/second_read.py | tests/test_engine.py::test_misread_amount_escalates | KPI 'Doble lectura 20/25, 0 contradice' |
| Cuenta del registro maestro: guard/approval.py approve() usa beneficiaries[...] | guard/approval.py approve() usa beneficiaries[...]['cuenta'] | tests/test_approval.py::test_approve_25_pays_master_account_not_new_one | factura 25: 'La factura pedía 000-FICT-9999' tachado |
| Re-chequeo al aprobar (imprest) + presupuesto atómico: guard/approval.py (transaction.atomic + select_for_update) | guard/approval.py (transaction.atomic + select_for_update) | tests/test_approval.py::test_approve_rechecks_budget | aprobar la 19 -> 'presupuesto insuficiente' |
| Recibo HMAC de un solo uso: guard/receipt.py verify() | guard/receipt.py verify() | tests/test_receipt.py | detalle -> 'Alterar monto' -> sello rojo |
| Separación de funciones: guard/approval.py _require_other_person | guard/approval.py _require_other_person | tests/test_approval.py::test_requester_cannot_approve_own_request | aprobar como ap@lumbre.example -> bloqueado |
| Montos Decimal, sin float: todo guard/ | todo guard/ | tests/test_no_float.py | — |
| Casos límite exactos: guard/engine.py | guard/engine.py | tests/test_limits.py | — |
| Inyección: guard/extractor.py is_suspicious + R_SOSPECHA | guard/extractor.py is_suspicious + R_SOSPECHA | tests/test_extractor.py, tests/test_views.py::test_api_injection_escalates | factura 24 |
| Arena v1→v2: guard/arena.py | guard/arena.py | tests/test_arena.py | tablero -> 'Correr arena' |
| Corrección humana re-evalúa: guard/services.py correct_field | guard/services.py correct_field | tests/test_corrections.py | detalle -> 'Corregir campo' |

## Extractor: modelo propio vs base vs Claude

| Extractor | Monto+moneda | Beneficiario (texto) | Beneficiario resuelto | Cuenta | Fecha | Total | Costo |
| Qwen2.5-1.5B base | 96% | 64% | 80% | 68% | 88% | 79% | US$0 (CPU) |
| Qwen2.5-1.5B afinado (propio) | 100% | 80% | 96% | 100% | 96% | 94% | US$0 (CPU, ~6 s/factura) |
| Claude Sonnet 4.6 | 100% | 88% | — | 100% | 92% | 95% | por token |

Con lecturas en vivo del modelo propio el motor decide 25/25 y 0 pagos indebidos (tests/test_pipeline_qwen.py). La demo pública reproduce esas lecturas.

## Recibo firmado

Cada decisión lleva un recibo HMAC-SHA256 (factura, monto, moneda, beneficiario, cuenta del registro maestro, resultado, regla, versión de política, nonce, vence en 24 h). Al aprobar, el guardián verifica firma, vencimiento y nonce no usado; si falla no se emite borrador. El borrador incluye `receipt_sig`. En el detalle de factura, «Alterar monto» demuestra el rechazo.

## Ideas de open source (créditos)

- **AgentGate:** decisiones ALLOW / DENY / ESCALATE.
- **imprest:** re-chequear los límites duros al aprobar.
- **invoice2data:** plantillas regex para la segunda lectura (implementación propia, sin la dependencia).

## Roadmap

- Servidor MCP sobre la API de Blinka.
- Los mismos límites como políticas de gasto en la wallet USDC.
- Anclaje del registro con OpenTimestamps y hash encadenado del log.
- Aprobaciones por Slack.

## Licencia

MIT.
