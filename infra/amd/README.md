# infra/amd – self-hosted vLLM on AMD ROCm

**This folder is only for self-hosting.** During development scanota talks to the AMD Tokenfactory
API and needs nothing from here: set `LLM_BASE_URL` and `LLM_API_KEY` in `.env` and run
`make up`. Do not start the vLLM compose file for Tokenfactory.

| | AMD Tokenfactory (development) | Self-hosted vLLM (final demo) |
|---|---|---|
| Who runs the model | AMD, as a hosted API | You, on an AMD GPU (Developer Cloud / Instinct) |
| `LLM_BASE_URL` | `https://developer.amd.com.cn/radeon/api/v1` | `http://<vllm-host>:8080/v1` |
| Compose | `docker-compose.yml` only | `docker-compose.yml` + `infra/amd/docker-compose.vllm.yml` |
| Model names | Tokenfactory catalogue names | The `VLLM_MODEL` you serve (`--served-model-name`) |
| OCR endpoint (`/ocr`) | Available | **Not available**: set `OCR_ENABLED=false` |
| Rate limits (429) | Shared per team key: 30 RPM, 8 concurrent. Handled by retry | Your own hardware limits |

## Running vLLM yourself

Needs a machine with an AMD GPU and ROCm. Add to `.env`:

```
VLLM_IMAGE=rocm/vllm:latest        # pick a tag that matches your ROCm version
VLLM_MODEL=<huggingface model id>  # becomes the served model name
VLLM_PORT=8080
MAX_MODEL_LEN=8192
HUGGING_FACE_HUB_TOKEN=            # only for gated models
```

```bash
docker compose -f docker-compose.yml -f infra/amd/docker-compose.vllm.yml up -d
```

One vLLM container serves one model. The app uses a vision model for receipts and a text model
for chat, so either run a second container on another port or point `LLM_MODEL_VISION` and
`LLM_MODEL_TEXT` at the same multimodal model. Then switch the app over in `.env`:

```
LLM_BASE_URL=http://<vllm-host>:8080/v1
LLM_MODEL_VISION=<VLLM_MODEL>
LLM_MODEL_TEXT=<VLLM_MODEL>
OCR_ENABLED=false
```

If your vLLM version rejects `reasoning_effort`, set `LLM_REASONING_EFFORT_SQL=` and
`LLM_REASONING_EFFORT_TEXT=` to empty; `LLM_MAX_TOKENS_*` still bounds the output.

This overlay has never been run: the ROCm image tag and the GPU run are untested. The project
currently uses AMD Token Factory instead (see the main README).
