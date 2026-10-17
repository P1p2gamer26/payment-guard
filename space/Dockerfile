FROM python:3.11-slim
RUN pip install --no-cache-dir llama-cpp-python==0.3.16 "uvicorn" "fastapi" "sse-starlette" "starlette-context" "pydantic-settings" "huggingface_hub" \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
RUN useradd -m user
USER user
WORKDIR /home/user
COPY --chown=user start.py .
EXPOSE 7860
CMD ["python", "start.py"]
