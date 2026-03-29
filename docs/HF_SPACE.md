# Hugging Face Space configuration

This environment is deployed as a **Docker Space** with the OpenEnv FastAPI server on port **8000**.

## Recommended Space secrets

Configure these in the Space **Settings → Secrets and variables** so automated evaluation and `inference.py` can reach your LLM:

| Variable | Purpose |
| --- | --- |
| `API_BASE_URL` | OpenAI-compatible API base URL (for example `https://api.openai.com/v1` or `https://router.huggingface.co/v1`). |
| `MODEL_NAME` | Model identifier passed to the chat completions API. |
| `HF_TOKEN` | Hugging Face token with inference permissions, or use `OPENAI_API_KEY` for direct OpenAI access. |
| `ENV_BASE_URL` | **Optional** when running `inference.py` *outside* the Space: set to the Space public URL with scheme (for example `https://<user>-supportdesk-env.hf.space`) so the client talks to the deployed env. When the evaluator runs inference *inside* the same container, use `http://127.0.0.1:8000`. |

Never commit real tokens; use Space secrets or local `.env` files listed in `.gitignore`.

## Health and UI

- `GET /health` should return HTTP **200** for platform health checks.
- With `ENABLE_WEB_INTERFACE=true` (set in the [`Dockerfile`](../Dockerfile)), a Gradio UI is available at **`/web/`** (matches README `base_path: /web`).

## Deploy and verify

```bash
huggingface-cli login
uv run openenv push --repo-id <your-org>/<space-name>
```

After build:

```bash
curl -fsS "https://<your-space-url>/health"
```

Run the packaged validation script locally before submitting:

```bash
./scripts/validate_submission.sh
```
