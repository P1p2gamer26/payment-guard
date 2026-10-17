---
title: Payment Guard Extractor
emoji: 🧾
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

Servidor OpenAI-compatible (llama.cpp) del extractor de facturas de Payment Guard.
Solo extrae campos; nunca decide pagos.

Variables (Settings > Variables): `MODEL_REPO` (default `P1p2gamer26/payment-guard-extractor-0.5b`).
Si ese repo no existe o no tiene .gguf, sirve el Plan B `Qwen/Qwen2.5-0.5B-Instruct-GGUF` (base).

Django: `LLM_BASE_URL=https://p1p2gamer26-payment-guard.hf.space/v1`, `LLM_MODEL=payment-guard`.
