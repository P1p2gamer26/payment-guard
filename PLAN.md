# Payment Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per Julian's CLAUDE.md: tasks >20 lines go to `~/bin/codexr --sandbox workspace-write "<prompt>"` (run from repo root, timeout 600000); Claude reviews `git diff`, runs `./verify.sh`, `/security-review` on Tasks 4, 6, 8.

**Goal:** Un agente que lee facturas de Lumbre Analytics (ficticia) y decide PAGAR / FRENAR / ESCALAR con reglas en código, explica cada decisión, pide aprobación humana y emite un borrador de pago formato Blinka sin ejecutarlo.

**Architecture:** El LLM solo extrae campos (con casete grabado para replay sin red) y una segunda lectura por regex debe coincidir en monto y moneda ("doble llave"). Un motor puro `decide()` aplica las reglas con default-deny; la aprobación humana vuelve a chequear límites duros (idea de imprest). Django + SQLite sirve tablero, bandeja de aprobación, registro y `/api/evaluate`.

**Tech Stack:** Python 3.13, Django 5.2, SQLite, whitenoise, stdlib `urllib` para el LLM (OpenAI-compatible, 9Router local), pytest + pytest-django, Playwright (1 E2E). Extra opcional: `opentimestamps-client`.

**Spec:** `C:\Users\Julian\Downloads\hackaton x30\blinka\ESTRATEGIA.md` (+ `brief-blinka.md`, `05-prd-demo.md`, `06-implementabilidad-verificador.md`, `datos/`)

## Global Constraints

- Repo NUEVO y público: `C:\Users\Julian\Downloads\payment-guard` (regla del hackathon: el proyecto empieza después del kickoff). Primer commit hoy.
- Entrega: subir a HackRadar antes del **dom 18-oct 11:00** (cierre 12:00). Código congelado dom 08:00.
- Decisiones: exactamente `"PAGAR" | "FRENAR" | "ESCALAR"`. El LLM nunca produce la decisión.
- **Cero PAGAR fuera de reglas.** Ante error, duda o excepción en cualquier paso ⇒ `ESCALAR`.
- Cuenta bancaria y beneficiario se toman del registro maestro (`reglas.json`), nunca de la factura.
- Montos con `decimal.Decimal`, nunca float. Conversión a USD con `tipos_cambio_a_usd` de `reglas.json`.
- Datos 100% ficticios; sin secretos en el repo (`.env` ignorado; `LLM_API_KEY` por entorno).
- `DECISION_MODE`: `live` | `record` | `replay` (default `replay`; el deploy SIEMPRE `replay`, no hay 9Router en la nube).
- Prohibido editar `verify.sh`, `tests/test_golden.py` y `data/esperado.json` después del Task 1 salvo pedido explícito de Julian.
- UI en español; Django autoescape (sin `|safe` ni `mark_safe` con datos de facturas).
- Atajos deliberados marcados `# ponytail:`.

## Review Focus

1. Monto con formato latino ambiguo (`1.250,00` vs `1,250.00`, `COP 8.800.000`) → la doble lectura lo detecta y ESCALA; nunca PAGAR con monto mal leído. Test en Task 3.
2. Casete inexistente en modo `replay` (factura nueva subida en el demo desplegado) → ESCALAR con razón "no se pudo leer sin conexión", sin 500. Test en Task 4.
3. Aprobar un ESCALADO cuando el presupuesto ya no alcanza (otro pago se aprobó antes) → la aprobación se rechaza con motivo; no se genera borrador. Test en Task 6.
4. Editar reglas (bajar umbral 3000→2000) y reprocesar → nueva versión de política; decisiones viejas conservan su versión. Test en Task 5.
5. LLM devuelve JSON inválido o con un campo extra `"decision"` → se ignora el extra / ESCALAR por esquema inválido. Test en Task 4.

---

### Task 1: Repo, esqueleto desplegado y datos dorados

**Files:**
- Create: `payment-guard/` (Django project `config/`, app `guard/`), `requirements.txt`, `.gitignore`, `.env.example`, `verify.sh`, `CLAUDE.md`, `README.md` (stub)
- Create: `data/reglas.json`, `data/facturas/01..25.*`, `data/esperado.json` (copiados de `hackaton x30/blinka/datos/`)
- Create: `data/extracciones_gold.json`
- Modify: `data/esperado.json` — ids `17` y `18` pasan de `FRENAR` a `ESCALAR` (decisión: beneficiario nuevo y monto que no cuadra los puede aprobar una persona); `data/reglas.json` `prioridad_decision` acorde
- Test: `tests/test_data.py`

**Interfaces:**
- Produces: `data/extracciones_gold.json` = lista de objetos `{"invoice_id","beneficiary_name","beneficiary_id"|null,"amount":"<str decimal>","currency","issue_date":"YYYY-MM-DD","invoice_number","bank_account","concept","confidence":1.0,"suspicious":bool}` — la extracción correcta de cada factura (24 → `suspicious: true`).
- Produces: `guard/data.py`: `load_policy(path="data/reglas.json") -> Policy`, `load_gold() -> list[Extraction]`, `load_expected() -> dict[str, str]` (id → decisión). `Policy` y `Extraction` se definen en Task 2; aquí se crean como dataclasses en `guard/domain.py` con los campos de arriba y `Policy(raw: dict, version: int=1)` + propiedades `per_payment_limit_usd`, `approval_threshold_usd`, `period_budget_remaining_usd`, `allowed_currencies`, `fx: dict[str, Decimal]`, `contract_tolerance_pct`, `max_age_days`, `today: date`, `beneficiaries: dict[str, dict]` (por id).

- [ ] **Step 1:** `git init`, venv, `pip install django==5.2.* whitenoise pytest pytest-django`; `django-admin startproject config .`; `startapp guard`; settings con `DEBUG` y `SECRET_KEY` por entorno, whitenoise, `ALLOWED_HOSTS` por entorno.
- [ ] **Step 2:** `verify.sh` = `pytest -q && echo OK`; `CLAUDE.md` con las Global Constraints y "no tocar verify.sh / test_golden / esperado.json".
- [ ] **Step 3:** Copiar datos; aplicar el cambio 17/18; escribir `extracciones_gold.json` leyendo cada factura a mano (es el oráculo, no lo genera el LLM).
- [ ] **Step 4: Write the failing test** `tests/test_data.py`:
```python
def test_data_consistent():
    gold = load_gold(); exp = load_expected()
    assert len(gold) == 25 and set(exp) == {g.invoice_id for g in gold}
    assert list(exp.values()).count("PAGAR") == 14
    assert exp["17"] == exp["18"] == "ESCALAR"
    assert load_policy().per_payment_limit_usd == Decimal("6000")
```
- [ ] **Step 5:** Run `pytest tests/test_data.py -v` → FAIL; implementar `guard/data.py` + `guard/domain.py`; → PASS.
- [ ] **Step 6:** Vista `/` "Payment Guard — en construcción"; deploy a PythonAnywhere (cuenta gratis, sin tarjeta; Julian crea la cuenta él mismo) con `DECISION_MODE=replay`. Verificar la URL desde el celular.
- [ ] **Step 7:** Repo público en GitHub `P1p2gamer26/payment-guard`; commit `feat: esqueleto, datos dorados y deploy`; push.

### Task 2: Motor de reglas y verificador dorado

**Files:**
- Create: `guard/engine.py`
- Test: `tests/test_golden.py`, `tests/test_engine.py`

**Interfaces:**
- Consumes: `Policy`, `Extraction`, `load_gold`, `load_expected` (Task 1).
- Produces: `guard/engine.py`:
  - `@dataclass Decision(invoice_id: str, outcome: str, rule: str, amount_usd: Decimal|None, facts: dict)` — `facts` = valores comparados (p. ej. `{"monto_usd": "7000", "limite": "6000"}`) para la explicación.
  - `@dataclass Ledger(remaining_usd: Decimal, paid: list[Extraction])`
  - `decide(x: Extraction, p: Policy, ledger: Ledger, second_read: tuple[Decimal, str] | None = None) -> Decision` — pura, sin I/O.
  - `run_batch(xs: list[Extraction], p: Policy) -> list[Decision]` — en orden de `invoice_id`; solo PAGAR descuenta de `ledger.remaining_usd` y se agrega a `ledger.paid`.
  - `allowed_to_pay(x, p, ledger) -> bool` — oráculo independiente (reimplementa límites duros por separado, sin reutilizar `decide`).
  - Códigos de regla (`rule`): `R_SOSPECHA, R_CONFIANZA, R_DOBLE_LECTURA, R_MONEDA, R_BENEFICIARIO, R_CUENTA, R_DUPLICADO, R_FECHA, R_CONTRATO, R_LIMITE, R_PRESUPUESTO, R_UMBRAL, OK`.

Orden de evaluación (el primero que dispara gana; default-deny):

| # | Condición | Resultado |
|---|---|---|
| 1 | `x.suspicious` | ESCALAR `R_SOSPECHA` |
| 2 | `x.confidence < 0.8` | ESCALAR `R_CONFIANZA` |
| 3 | `second_read` presente y difiere en monto o moneda | ESCALAR `R_DOBLE_LECTURA` |
| 4 | moneda ∉ permitidas | FRENAR `R_MONEDA` |
| 5 | beneficiario no está en el registro | ESCALAR `R_BENEFICIARIO` |
| 6 | `bank_account` ≠ cuenta registrada | ESCALAR `R_CUENTA` |
| 7 | mismo `invoice_number`+beneficiario, o mismo beneficiario+concepto normalizado+mes ya en `ledger.paid` | FRENAR `R_DUPLICADO` |
| 8 | fecha futura o > `antiguedad_maxima_dias` | FRENAR `R_FECHA` |
| 9 | \|monto − contrato\| > tolerancia % (si hay contrato) | ESCALAR `R_CONTRATO` |
| 10 | monto_usd > límite por pago | FRENAR `R_LIMITE` |
| 11 | monto_usd > umbral aprobación | ESCALAR `R_UMBRAL` (la aprobación re-chequea presupuesto, Task 6) |
| 12 | monto_usd > `ledger.remaining_usd` | FRENAR `R_PRESUPUESTO` |
| 13 | — | PAGAR `OK` |

- [ ] **Step 1: Write the failing test** `tests/test_golden.py` (el verificador; no se edita después):
```python
def test_golden_25():
    decisions = run_batch(load_gold(), load_policy())
    got = {d.invoice_id: d.outcome for d in decisions}
    assert got == load_expected()

def test_every_pagar_passes_oracle():
    p = load_policy(); ledger = Ledger(p.period_budget_remaining_usd, [])
    for x in sorted(load_gold(), key=lambda g: g.invoice_id):
        d = decide(x, p, ledger)
        if d.outcome == "PAGAR":
            assert allowed_to_pay(x, p, ledger)
            ledger.remaining_usd -= d.amount_usd; ledger.paid.append(x)
```
- [ ] **Step 2:** `pytest tests/test_golden.py -v` → FAIL.
- [ ] **Step 3:** Implementar `engine.py` según la tabla.
- [ ] **Step 4:** `tests/test_engine.py`: `test_exception_in_rule_escalates` (monkeypatch de una regla que lanza → ESCALAR, no PAGAR); `test_lower_threshold_escalates_06` (umbral 2000 ⇒ factura 06 USD 2,500 → ESCALAR `R_UMBRAL`).
- [ ] **Step 5:** `./verify.sh` → `OK`. Commit `feat: motor de reglas + verificador dorado`.

### Task 3: Segunda lectura (doble llave)

**Files:**
- Create: `guard/second_read.py`
- Test: `tests/test_second_read.py`

**Interfaces:**
- Produces: `read_total(text: str) -> tuple[Decimal, str] | None` — monto total y moneda por regex. `None` si no hay exactamente un candidato claro.
  `# ponytail: regex propia al estilo invoice2data (plantillas por formato); invoice2data como dependencia si se agregan PDFs reales.`
- Consumes: `decide(..., second_read=...)` (Task 2): `None` ⇒ no bloquea pero baja confianza en Task 4.

- [ ] **Step 1: Write the failing test**:
```python
@pytest.mark.parametrize("text,expected", [
  ("Total: USD 1,200.00", (Decimal("1200.00"), "USD")),
  ("Valor: COP 8.800.000", (Decimal("8800000"), "COP")),
  ("Total a pagar $ 1.250,00 MXN", (Decimal("1250.00"), "MXN")),
])
def test_read_total(text, expected): assert read_total(text) == expected

def test_ambiguous_returns_none(): assert read_total("USD 1,250 o 1.250?") is None

def test_misread_amount_escalates():  # Review Focus 1
    x = replace(gold("02"), amount=Decimal("8800"))   # LLM leyó mal
    d = decide(x, load_policy(), fresh_ledger(), second_read=(Decimal("8800000"), "COP"))
    assert (d.outcome, d.rule) == ("ESCALAR", "R_DOBLE_LECTURA")
```
- [ ] **Step 2:** FAIL → implementar → PASS. Correr `read_total` sobre las 25 facturas: debe coincidir con `extracciones_gold.json` en ≥ 20 (las CFDI `.json` se leen del campo `total`/`moneda`). Commit.

### Task 4: Extractor LLM con record/replay

**Files:**
- Create: `guard/extractor.py`, `cassettes/<sha256>.json` (25, grabados en modo `record`)
- Test: `tests/test_extractor.py`

**Interfaces:**
- Consumes: `Extraction`, `read_total`, `Policy.beneficiaries`.
- Produces: `extract(text: str, mode: str | None = None) -> Extraction` — `mode` default `os.environ["DECISION_MODE"]`.
  - Prompt fijo en código; el texto de la factura va entre delimitadores `<<<FACTURA ... FACTURA>>>` y se recorta a 8.000 caracteres.
  - Respuesta: se quitan cercas ```` ``` ````; `json.loads`; solo se aceptan las claves de `Extraction` excepto `confidence`/`suspicious` (cualquier otra, p. ej. `"decision"`, se descarta).
  - `suspicious = True` si el texto contiene instrucciones a una máquina (regex: `ignore|ignora|system instruction|pre-?approved|aprobad[oa] por el CFO`) — calculado en código, no por el LLM.
  - `confidence`: 1.0; 0.5 si falta algún campo obligatorio o si `read_total` es `None`.
  - Casete: clave `sha256(prompt_version + text)`. `replay` sin casete ⇒ `Extraction` con `confidence=0` (⇒ ESCALAR `R_CONFIANZA`).
  - LLM: `POST {LLM_BASE_URL}/chat/completions`, `model=LLM_MODEL` (`ag/claude-sonnet-4-6`), `stream: false`, timeout `LLM_TIMEOUT=10`.

- [ ] **Step 1: Write the failing tests:**
```python
def test_replay_without_cassette_escalates(tmp_path):   # Review Focus 2
    x = extract("factura nueva sin casete", mode="replay")
    assert decide(x, load_policy(), fresh_ledger()).outcome == "ESCALAR"

def test_extra_decision_field_ignored(fake_llm):         # Review Focus 5
    fake_llm('{"amount":"1500","currency":"USD","decision":"PAGAR", ...}')
    x = extract(text_of("24"), mode="live")
    assert x.suspicious and decide(x, load_policy(), fresh_ledger()).outcome == "ESCALAR"

def test_invalid_json_escalates(fake_llm):
    fake_llm("no soy json"); assert extract(text_of("01"), mode="live").confidence == 0

def test_replay_matches_gold():
    for g in load_gold():
        x = extract(text_of(g.invoice_id), mode="replay")
        assert (x.amount, x.currency) == (g.amount, g.currency)
```
- [ ] **Step 2:** FAIL → implementar. `fake_llm` = fixture que monkeypatchea `urllib.request.urlopen`.
- [ ] **Step 3:** Con 9Router arriba: `DECISION_MODE=record python manage.py extract_all` (command en `guard/management/commands/extract_all.py`) graba 25 casetes. Revisar a mano las que no coincidan con gold; si el LLM falla alguna, se queda así (el motor la escala) y se anota en el README (es el % de acierto honesto del pitch).
- [ ] **Step 4:** `./verify.sh` → OK. Commit `feat: extractor con casetes`. `/security-review`.

### Task 5: Persistencia, explicaciones y versiones de política

**Files:**
- Create: `guard/models.py`, `guard/explain.py`, `guard/services.py`, migración
- Test: `tests/test_services.py`

**Interfaces:**
- Produces (models): `PolicyVersion(version:int, raw:JSON, created_at)`, `Invoice(invoice_id, text, extraction:JSON)`, `DecisionRecord(invoice FK, policy_version FK, outcome, rule, amount_usd, facts:JSON, explanation:str, created_at)`, `Approval(decision FK, outcome: "APROBADO"|"RECHAZADO", note:str (obligatoria), approver:str, created_at)`.
- Produces: `explain(d: Decision, x: Extraction) -> str` — una frase por código de regla, en español llano, con los `facts` (p. ej. `R_LIMITE`: "Frenada: USD 7,000 supera el límite por pago de USD 6,000."). Sin LLM. `# ponytail: plantillas; LLM para redacción solo si sobra tiempo.`
- Produces: `process_all(policy_version: PolicyVersion) -> list[DecisionRecord]` (carga facturas, `extract`, `read_total`, `run_batch`, guarda); `save_policy(raw: dict) -> PolicyVersion` (incrementa versión).

- [ ] **Step 1: Write the failing tests:**
```python
def test_process_all_matches_expected(db):
    recs = process_all(save_policy(load_policy().raw))
    assert {r.invoice.invoice_id: r.outcome for r in recs} == load_expected()
    assert all(r.explanation for r in recs)

def test_new_policy_version_keeps_old(db):               # Review Focus 4
    v1 = save_policy(load_policy().raw); process_all(v1)
    raw = deepcopy(v1.raw); raw["reglas_pago"]["umbral_aprobacion_humana_usd"] = 2000
    v2 = save_policy(raw); process_all(v2)
    assert DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=v1).outcome == "PAGAR"
    assert DecisionRecord.objects.get(invoice__invoice_id="06", policy_version=v2).outcome == "ESCALAR"
```
- [ ] **Step 2:** FAIL → implementar → PASS → commit.

### Task 6: Aprobación humana y borrador de pago Blinka

**Files:**
- Create: `guard/approval.py`
- Test: `tests/test_approval.py`

**Interfaces:**
- Consumes: `DecisionRecord`, `Approval`, `allowed_to_pay`, `Policy`.
- Produces: `approve(record: DecisionRecord, approver: str, note: str) -> dict` (devuelve el borrador) y `reject(record, approver, note) -> Approval`.
  - Solo registros `ESCALAR`; `note` vacía ⇒ `ValueError`.
  - **Re-chequeo de límites duros al aprobar** (idea de imprest): moneda, límite por pago y presupuesto restante de esa versión de política (contando PAGAR + aprobados). Si no pasa ⇒ `ValueError("no se puede aprobar: <motivo>")` y no hay borrador.
  - Borrador (vocabulario de la API de Blinka, montos en unidades menores):
```json
{"object":"transfer_draft","status":"draft_not_executed","amount_minor":150000,
 "currency":"USD","beneficiary_id":"B07","beneficiary_account":"<del registro maestro>",
 "rail":"ACH|SWIFT|SPEI|BRE_B","invoice_id":"24","policy_version":1,
 "approved_by":"cfo@lumbre.example","approval_note":"...","created_at":"ISO-8601 UTC"}
```
  `rail` por país: US→`ACH`, CO→`BRE_B`, MX→`SPEI`, otro→`SWIFT`.

- [ ] **Step 1: Write the failing tests:**
```python
def test_approve_creates_draft_from_master_account(db, processed):
    d = approve(rec("19"), "cfo@lumbre.example", "ok, búsqueda senior acordada")
    assert d["status"] == "draft_not_executed" and d["beneficiary_account"] == master_account("19")

def test_approve_rechecks_budget(db, processed):          # Review Focus 3
    exhaust_budget()   # aprueba/paga hasta dejar < monto de 19
    with pytest.raises(ValueError, match="presupuesto"):
        approve(rec("19"), "cfo@lumbre.example", "ok")

def test_note_required(db, processed):
    with pytest.raises(ValueError): approve(rec("19"), "cfo@lumbre.example", "")
```
- [ ] **Step 2:** FAIL → implementar → PASS → commit. `/security-review`.

### Task 7: Pantallas

**Files:**
- Create: `guard/views.py`, `guard/urls.py`, `guard/templates/guard/{base,board,detail,rules,inbox,log}.html`, `guard/static/guard/app.css`
- Test: `tests/test_views.py`, `tests/e2e/test_demo.py` (Playwright)

**Interfaces:**
- Consumes: `process_all`, `save_policy`, `approve`, `reject`, `explain`.
- Produces (rutas): `/` tablero (3 columnas PAGAR / FRENAR / ESCALAR + métricas: autonomía = PAGAR+FRENAR correctos / 25, "Pagos indebidos: 0" = conteo de PAGAR donde `allowed_to_pay` es falso, coincidencias con esperado), `/factura/<id>/` (texto original, extracción, regla, valores vs umbral, explicación), `/reglas/` (form de límites, umbral, monedas, beneficiarios ⇒ `save_policy` + `process_all`), `/aprobaciones/` (ESCALAR pendientes con aprobar/rechazar + nota), `/registro/` (tabla + `?format=csv`), `POST /demo/reiniciar/` (borra y reprocesa con política v1).
  Diseño plano primero (W5: "como un TXT"), luego CSS mínimo. Funciona en móvil.

- [ ] **Step 1: Write the failing tests:** `test_board_shows_counts` (política dorada: PAGAR 14, FRENAR 6, ESCALAR 5), `test_csv_export_has_25_rows`, `test_invoice_text_is_escaped` (factura 24 renderiza `&lt;`/sin ejecutar HTML), `test_rules_edit_reprocesses`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3:** E2E `test_demo.py`: abrir `/`, ver "Pagos indebidos: 0", ir a `/aprobaciones/`, aprobar la 19 con nota, ver borrador `draft_not_executed`. `./verify.sh` (agregar `pytest tests/e2e` al final de verify.sh SOLO en este paso, con permiso de Julian) → OK. Commit.

### Task 8: API para otros agentes

**Files:**
- Modify: `guard/views.py`, `guard/urls.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `POST /api/evaluate` body `{"text": "<factura>"}` → `{"outcome","rule","explanation","policy_version"}`; usa la política vigente y un ledger con lo ya pagado. Sin auth: `# ponytail: demo pública; token por cabecera antes de un piloto.` Límite 20 KB del body.

- [ ] **Step 1:** Tests `test_api_injection_escalates` (texto de 24 → `ESCALAR`), `test_api_rejects_big_body` (413). FAIL → implementar → PASS → commit. `/security-review`.

### Task 9: Deploy estable, README y respaldo

**Files:**
- Modify: `README.md`, `requirements.txt`
- Create: `docs/arquitectura.md` (diagrama mermaid de ESTRATEGIA.md §3)

- [ ] **Step 1:** Deploy en PythonAnywhere con `DECISION_MODE=replay`, `DEBUG=0`, `collectstatic`; `python manage.py migrate && python manage.py shell -c "from guard.services import *; process_all(save_policy(load_policy().raw))"`.
- [ ] **Step 2:** Verificar en celular y en otro navegador: tablero, aprobación, CSV, `/api/evaluate` con curl.
- [ ] **Step 3:** README: problema (3 líneas), demo URL, cómo correr (`./verify.sh`), arquitectura, tabla de reglas, casos trampa y resultado, % de acierto real del extractor, costo por factura, límites honestos (no KYC/AML, no mueve dinero), créditos/ideas (AgentGate ALLOW/DENY/ESCALATE, imprest re-chequeo al aprobar, invoice2data plantillas), roadmap (MCP, Jev como freno asimétrico, límites en wallet USDC, hash encadenado).
- [ ] **Step 4:** Grabar video de respaldo del demo (Win+Shift+R). Commit `docs: README y deploy`. Tag `v1.0`. **Congelar código dom 08:00.**

### Task 10 (opcional, solo si Tasks 1–9 están verdes el sábado en la noche): Anclaje del registro en blockchain

**Files:**
- Create: `guard/anchor.py`, `anchors/` (archivos `.ots`)
- Modify: `guard/views.py` (botón "Anclar registro" en `/registro/`)
- Test: `tests/test_anchor.py`

**Interfaces:**
- Produces: `log_digest(policy_version: int) -> str` (sha256 del CSV del registro, determinista) y `anchor(digest: str) -> Path` que llama `ots stamp` (OpenTimestamps: ancla en Bitcoin vía calendarios públicos, **gratis, sin wallet ni llaves**). `# ponytail: OpenTimestamps en vez de contrato en Base Sepolia — cero secretos, cero faucet.`

- [ ] **Step 1:** Tests: `test_digest_deterministic`, `test_digest_changes_if_log_tampered`. FAIL → implementar → PASS.
- [ ] **Step 2:** `pip install opentimestamps-client`; anclar el registro de la versión 1; guardar `.ots` en el repo; README explica cómo verificar (`ots verify`). En el pitch: "el registro queda sellado en Bitcoin; y para pagos USDC, los límites se imponen además en la wallet (políticas de gasto de Circle / session keys)". Commit.

---

## Tareas no-código (en paralelo, Julian)

| Cuándo | Qué | Fuente |
|---|---|---|
| sáb 12:00 | Post de validación en r/Accounting + LinkedIn (preguntas de `03-sponsor-oportunidades.md`) | W5 |
| sáb 15:00 | Mentoría de pitch (Zoom); preguntar FRENAR vs ESCALAR y nivel de autonomía aceptable | 03, 07 |
| sáb noche | Reel 1–2 "Construye en público" | 07-pitch.md |
| dom 08:00–09:00 | Llenar `{N}`, `{X}`, `{Z}%` del guion con métricas reales | 07-pitch.md |
| dom 09:00–10:30 | Grabar video 3:00 (skill `video-tutorial`, narración de Julian) | 07-pitch.md |
| dom antes 11:00 | HackRadar: crear equipo de 1, elegir reto Blinka, subir video + URL + repo | kickoff |
