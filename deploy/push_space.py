"""Sube space/ al Hugging Face Space. Uso: HF_TOKEN=... python deploy/push_space.py"""
import os

from huggingface_hub import HfApi

api = HfApi(token=os.environ["HF_TOKEN"])
repo = "P1p2gamer26/payment-guard"
api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
api.upload_folder(folder_path="space", repo_id=repo, repo_type="space")
print(f"https://huggingface.co/spaces/{repo}")
