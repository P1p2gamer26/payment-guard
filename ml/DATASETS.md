# Datos de entrenamiento

Mezcla `ml/train.jsonl` = 900 sinteticas LatAm (~70%) + 390 publicas (~30%), barajadas con seed 30.

| Fuente | Licencia | Uso | PII |
|---|---|---|---|
| `ml/gen_synthetic.py` (propio) | del repo | 900 facturas ficticias en formatos CO/MX/US/chat, ~5% con prompt injection | ninguna, todo ficticio |
| [katanaml-org/invoices-donut-data-v1](https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1) | MIT | campos (gt_parse) de facturas sinteticas generadas con Faker | ninguna real (nombres, direcciones, tax ids e IBAN generados) |
| [mychen76/invoices-and-receipts_ocr_v1](https://huggingface.co/datasets/mychen76/invoices-and-receipts_ocr_v1) | sin licencia declarada; es derivado directo del anterior (MIT) | solo el texto OCR de esas mismas facturas | igual que arriba |

Conversion (`ml/prep_public.py`): seller -> beneficiary_name (sin direccion), total_gross_worth -> amount (solo totales en `$` -> USD), iban -> bank_account, invoice_no, fecha mm/dd/aaaa -> ISO, primer item -> concept; beneficiary_id = null.

Evaluadas y descartadas: SROIE (licencia unknown/mixta, recibos de comercios reales), CORD-v2 (CC-BY-4.0, pero recibos reales sin nombre de beneficiario ni cuenta: no encaja en el esquema), HV09/synthetic-bilingual-invoices-200 (CC-BY, solo imagenes + arabe), Voxel51 receipts (imagenes).

Las 25 de `data/facturas` son solo evaluacion y nunca entran al train (el generador verifica que no haya coincidencias de beneficiario/cuenta).
