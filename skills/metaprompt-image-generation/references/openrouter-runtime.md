# OpenRouter Runtime

Use the bundled CLI as the only OpenRouter transport and Pillow for deterministic raster delivery. Run it as a black box after checking `--help`; do not rewrite its HTTP or conversion logic in the calling agent.

Install the image runtime once in the active Python environment:

```text
python3 -m pip install -r <skill-dir>/requirements.txt
```

## Configuration

Keep configuration in `<skill-dir>/.env`. Process environment variables take precedence over the file.

```dotenv
OPENROUTER_API_KEY=
OPENROUTER_IMAGE_MODEL=openai/gpt-image-2
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_APP_TITLE=Meta-Prompt Image Generation
OPENROUTER_HTTP_REFERER=
```

Create the untracked file with:

```text
python3 <skill-dir>/scripts/openrouter_image.py init
```

The command refuses to overwrite an existing `.env` and uses owner-only permissions on POSIX systems. Never print, copy into a request, or pass `OPENROUTER_API_KEY` on the command line.

Validate the key through OpenRouter's `/key` endpoint and confirm the configured image model without generating a paid image:

```text
python3 <skill-dir>/scripts/openrouter_image.py doctor
```

List currently available image models and their advertised capabilities:

```text
python3 <skill-dir>/scripts/openrouter_image.py models
```

## Generation request

Write a UTF-8 JSON object and pass its path to `generate --request`. Supported fields:

The distributed default is `openai/gpt-image-2`. Read [gpt-image-2.md](gpt-image-2.md) before adding model-specific fields; the table below describes the runner's cross-model interface, not a promise that every model accepts every field.

| Field | Requirement |
| --- | --- |
| `prompt` | Required non-empty compiled prompt. |
| `model` | Optional override; use only when the user explicitly selects a model. |
| `count` | Integer 1–100; defaults to 1. |
| `aspect_ratio` | `auto` or a positive `W:H` ratio supported by the model. |
| `resolution` | Model-supported resolution such as `1K`, `2K`, or `4K`. |
| `quality` | `auto`, `low`, `medium`, or `high`. |
| `output_format` | Final delivery format: `png` or `jpeg`; defaults to `png`. |
| `background` | `auto`, `transparent`, or `opaque`; transparency requires PNG or WebP. |
| `output_compression` | Integer 0–100; controls local JPEG quality and is ignored for PNG. |
| `seed` | Integer supported by the selected model. |
| `input_references` | List of local image paths, HTTPS URLs, or image data URLs. |
| `output_dir` | Caller-workspace destination; defaults to `generated-images`. |

Example:

```json
{
  "prompt": "Create a vertical editorial launch poster...",
  "count": 3,
  "aspect_ratio": "3:4",
  "quality": "high",
  "background": "opaque",
  "output_format": "png",
  "input_references": ["./hero-reference.png"],
  "output_dir": "./generated-images/campaign"
}
```

Local references resolve relative to the request JSON. Relative output directories resolve from the process working directory. The runner rejects output locations inside the installed skill.

Before generation, the runner queries `/images/models`, verifies the selected model, checks its declared input/output modalities, and rejects unsupported generation parameters. `output_format` is a delivery requirement: the runner forwards it only when advertised, then verifies and converts every returned raster with Pillow. If the model lacks multi-image `n`, the runner submits single-image calls until it saves the exact requested count.

## Manifest and failures

Success prints JSON containing `status`, `model`, `count`, absolute `files`, per-file `outputs`, final `output_format`, detected `provider_formats`, `transcoded`, effective `parameters`, aggregated `usage`, `request_count`, and non-secret `warnings`. Inspect only those files; never infer paths.

Exit codes:

- `0`: success.
- `2`: invalid local configuration, request, model, capability, or reference.
- `3`: OpenRouter authentication, HTTP, or network failure.
- `4`: malformed API response, invalid image bytes, or output-write failure.

The runner retries transient discovery failures and explicit transient HTTP errors. It does not retry ambiguous network failures on paid POST requests because the request may already have reached the provider.

## Agent compatibility

The package follows the common `SKILL.md` folder convention. Keep the folder unchanged:

- Codex and Antigravity: place under `.agents/skills/metaprompt-image-generation/`.
- Claude Code: copy or link under `.claude/skills/metaprompt-image-generation/`.
- Gemini CLI: place under `.gemini/skills/metaprompt-image-generation/` or link the folder with `gemini skills link <path>`.

Local shell-capable agents can run the bundled script. Hosted environments that block outbound network access can still compile the production prompt but cannot execute OpenRouter. Do not claim generation in that state.

OpenRouter API contract: <https://openrouter.ai/docs/guides/overview/multimodal/image-generation>
