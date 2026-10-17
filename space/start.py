import os
import subprocess
import sys

from huggingface_hub import hf_hub_download, list_repo_files

REPO = os.environ.get("MODEL_REPO", "P1p2gamer26/payment-guard-extractor-0.5b")
FALLBACK = ("Qwen/Qwen2.5-0.5B-Instruct-GGUF", "qwen2.5-0.5b-instruct-q4_k_m.gguf")  # Plan B: modelo base


def get_model():
    try:
        f = next(x for x in list_repo_files(REPO) if x.endswith(".gguf"))
        return hf_hub_download(REPO, f)
    except Exception as e:
        print(f"[plan B] {REPO} no disponible ({e}); sirviendo base", flush=True)
        return hf_hub_download(*FALLBACK)


path = get_model()
sys.exit(subprocess.call([sys.executable, "-m", "llama_cpp.server", "--model", path, "--model_alias", "payment-guard",
                          "--host", "0.0.0.0", "--port", "7860", "--n_ctx", "4096", "--chat_format", "chatml"]))
