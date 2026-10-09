# N-ATLaS inference on Modal

Aabo runs the official NCAIR1 model weights through a private, authenticated
gateway on Modal. Railway remains the public application boundary; browsers
and telephony providers never receive the Modal API credential.

## Deployed components

- `NCAIR1/N-ATLaS` runs through vLLM on an A10 GPU, with L4 as a fallback.
- English, Hausa, Igbo, and Yoruba ASR use their separate NCAIR1 Whisper Small
  checkpoints on four CPU cores.
- Model downloads are cached in the `natlas-hf-cache` Modal Volume.
- The deployment scales to zero and remains warm for twenty minutes after use.

The deployment is based on
[`Kambah123/N-ATLAS-Kit`](https://github.com/Kambah123/N-ATLAS-Kit) at commit
`16d449c1ec9e483e1f151c15224d4694b6366dce`. That project provides the gateway,
audio normalization, ASR routing, vLLM launcher, request authentication, and
privacy-safe request logging.

## Required configuration

Modal secrets:

| Name | Key | Purpose |
|---|---|---|
| `natlashf` | `HF_TOKEN` | Read access to the five gated NCAIR1 repositories |
| `natlas-api` | `NATLAS_API_KEYS` | Gateway bearer credential |

Railway variables:

| Name | Purpose |
|---|---|
| `NATLAS_BASE_URL` | Modal gateway origin, without `/v1` |
| `NATLAS_API_KEY` | One key also present in `NATLAS_API_KEYS` |
| `TRANSCRIPTION_TIMEOUT_SECONDS` | Set to `180` to accommodate a cold start |

The gateway credential and Hugging Face token must never be committed.

## Upstream deployment adjustments

The active Modal account uses the secret name `natlashf`, so both
`serve/modal_preflight.py` and `serve/modal_app.py` set:

```python
SECRET_NAME = "natlashf"
```

The vLLM base image already contains files under `/root/.cache/huggingface`.
Modal Volumes cannot mount over a non-empty image directory, so the deployment
sets this empty mount path instead:

```python
HF_CACHE_DIR = "/models/huggingface"
```

Without that adjustment, containers fail before model initialization with
`cannot mount volume on non-empty path`.

## Reproducing the deployment

```powershell
git clone https://github.com/Kambah123/N-ATLAS-Kit.git .natlas-kit
Set-Location .natlas-kit
git checkout 16d449c1ec9e483e1f151c15224d4694b6366dce
```

Apply the two adjustments above, then verify access and hardware before the
full deployment:

```powershell
modal run serve/modal_preflight.py --skip-gpu
modal run serve/modal_preflight.py
modal deploy serve/modal_app.py
```

The preflight must confirm all five gated repositories and sufficient GPU
memory. A healthy deployment returns all four ASR routes from `GET /health`.

## Operational warm-up

Run one short transcription in the first expected language 10–15 minutes
before a presentation. This loads both the container and the lazily loaded ASR
checkpoint; `GET /health` alone does not load a speech model. The twenty-minute
warm window keeps the presentation out of the cold-start path. Do not set
`min_containers=1` permanently; an always-warm GPU consumes the monthly credit
continuously.

The browser Language Lab sends 16 kHz mono WAV audio to Aabo. Aabo forwards it
to `POST /v1/audio/transcriptions` with the selected language, then returns the
transcript together with the exact model, provider, latency, and fallback flag.

### ASR quality safeguards

The browser requests mono audio with echo cancellation, noise suppression, and
automatic gain control. Leading and trailing silence are trimmed, and each web
report is capped at 20 seconds to stay comfortably inside Whisper's 30-second
window. Modal uses deterministic decoding with a four-token no-repeat
constraint and a repetition penalty. Aabo also detects repeated phrase loops;
a looping N-ATLaS result is rejected and routed to the configured Whisper
fallback instead of being presented as a valid transcript.
