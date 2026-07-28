# GPT Image 2 Profile

Use `openai/gpt-image-2` as the package default. Treat live `/images/models` discovery as authoritative; this profile records the intended prompting and parameter policy.

## User brief

When the skill is invoked alone or major specifications are missing, ask once for image size or destination, count, quality, rough prompt, and references when relevant. Keep the intake brief; the user does not need to know API fields.

Extract creative constraints from the rough prompt, then infer everything else:

- purpose and destination, such as social post, product page, poster, or presentation;
- subject and required action;
- exact visible text, copied verbatim;
- required brand colors, objects, people, logos, and exclusions;
- reference images and what each one controls;
- requested count.

Do not expand the intake into separate questions about composition, camera, lighting, palette, mood, or exclusions. Ask again only when a required reference is missing or unresolved taste would materially change the result. Otherwise choose the settings below autonomously.

## Current OpenRouter controls

The model currently advertises:

- `aspect_ratio`: `1:1`, `3:2`, `2:3`, `4:3`, `3:4`, `16:9`, `9:16`, `21:9`, or `auto`;
- `quality`: `auto`, `low`, `medium`, or `high`;
- `background`: `auto` or `opaque`;
- `n`: 1–10 images per request;
- `input_references`: 0–16 images;
- `output_compression`: integer 0–100.

Do not send `resolution`, `seed`, or transparent background unless live discovery begins advertising that field. GPT Image 2 currently does not expose arbitrary pixel dimensions or a selectable output format through OpenRouter. Treat `output_format` as the runner's delivery requirement: forward it only if live discovery adds support, otherwise transcode locally.

## Setting policy

- Infer aspect ratio from destination. Use `1:1` when no destination or orientation is implied.
- Use `high` quality for final deliverables. Use `medium` for ordinary iteration and `low` only when the user explicitly prioritizes speed or cost.
- Use `opaque` background. This model currently does not advertise transparency.
- Deliver PNG by default. Deliver JPEG only when the user requests it.
- Generate one image unless the user requests a batch. Preserve exact requested count; the runner can send up to 10 per call.
- Omit output compression unless the user requests JPEG compression; local JPEG encoding defaults to quality 90.
- Include only references that control identity, product geometry, composition, or style. State each reference's role in the prompt.

## Size interpretation

Translate “size” into an advertised aspect ratio. Do not promise exact pixels or 1K/2K/4K output. If exact delivery dimensions matter, generate at the correct aspect ratio, inspect the returned dimensions, then resize or crop outside the generation model with the user's approval when that post-processing is in scope.
