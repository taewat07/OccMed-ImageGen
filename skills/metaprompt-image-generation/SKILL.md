---
name: metaprompt-image-generation
description: Guide users through a short image-specification intake, turn their rough prompt and major output requirements into a production-ready prompt, then generate or edit images through OpenRouter, defaulting to OpenAI GPT Image 2. Use when an agent needs to generate, edit, restyle, composite, or create coordinated image variants; invoke OpenRouter image generation from Codex, Claude Code, Gemini CLI, Antigravity, or another shell-capable agent; preserve reference identity or layout; handle image typography; or adapt a visual brief to a model's supported parameters.
---
# Meta-Prompt Image Generation

Act as both Prompt Architect and Image Executor. Treat these as logical roles inside one agent; a multi-agent runtime is unnecessary. Use the bundled OpenRouter runner for deterministic API access rather than rebuilding HTTP calls.

Start with a compact specification intake when the user invokes the skill without a complete brief. Then convert the user's rough intent into a precise visual contract, compile it into the image tool's native input, execute the real tool, and verify the result. Never simulate tool use or claim an image was generated when it was not.

## Operating rules

- Run the guided intake when the user invokes the skill alone or has not supplied the major generation specifications.
- Ask once for the missing major specifications. Do not conduct a long creative questionnaire.
- Generate or edit immediately when the major specifications and rough prompt are clear.
- After intake, ask another question only when a required source image is missing or a genuine taste decision would materially change the result.
- Treat explicit user requirements as hard constraints. Never let house style, examples, or aesthetic defaults override them.
- Make technical and artistic decisions autonomously when the user leaves them open.
- Inspect the actual tool schema before constructing arguments. Never invent unsupported parameters.
- Keep private chain-of-thought private. Share only the useful brief, result, and material limitations.
- Use the smallest reference-image set that contains every required source.
- Keep API keys in the package-local `.env`. Never request that a user paste a key into chat, place a key in a prompt, or pass a key as a command argument.
- Use the configured OpenRouter image model unless the user explicitly requests a different model.
- Never silently fall back to another provider.

## Workflow

### 1. Run the guided intake

When the skill is invoked without a complete brief, briefly explain that the agent will handle creative and API details, then ask for only:

1. Image size, aspect ratio, or destination.
2. Number of images.
3. Quality: low, medium, or high.
4. Rough prompt or central idea.
5. Reference images, only when editing, compositing, or preserving identity, geometry, or layout.

Use one compact message. Give short examples for size such as `16:9 website hero`, `9:16 story`, or `1:1 square`. Explain that exact pixel dimensions map to the closest supported aspect ratio and may require resizing after generation. Do not ask separately about camera, lighting, palette, mood, composition, exclusions, or typography; extract those from the rough prompt and decide unresolved creative details autonomously.

Do not ask the user to repeat information already present. Accept “use defaults” for any omitted field. Apply these defaults:

- count: `1`;
- quality: `high`;
- aspect ratio: infer from destination, otherwise `1:1`;
- background: `opaque` for GPT Image 2;
- output format: `png`.

After the user responds, proceed without another confirmation unless a required reference is absent or the host environment requires approval for network or paid execution.

### 2. Classify the operation

Choose exactly one primary operation:

- `generate`: create a new image from text.
- `edit`: change an existing image while preserving specified content.
- `composite`: combine two or more references into one coherent image.
- `variation`: produce a defined number of coordinated alternatives.

An edit or composite requires access to every source image. If a required image is absent, stop and request that image.

### 3. Build the visual intent contract

Extract four constraint groups before writing the image prompt:

- **Must satisfy:** subject, action, exact text, brand elements, count, aspect ratio, and required objects.
- **Must preserve:** identity, pose, product geometry, logo, layout, background regions, or other reference details.
- **May decide:** composition, lens, lighting, palette, texture, styling, and secondary details not fixed by the user.
- **Must avoid:** unwanted objects, accidental text, visual clichés, identity drift, layout drift, and prohibited content.

Record which reference supplies each identity, object, layout, or style. Never use a style reference as permission to copy unrelated content.

Read [references/prompt-compiler.md](references/prompt-compiler.md) before compiling the prompt.

### 4. Form one creative direction

Resolve open visual decisions into one coherent direction. Internally define:

- communication goal and audience;
- focal subject and visual hierarchy;
- environment and spatial relationships;
- composition and camera language;
- lighting, palette, materials, and mood;
- typography and exact copy, when present;
- continuity rules across variants.

Do not produce a decorative plan that has no effect on execution. Every material design decision must appear in the compiled prompt or tool arguments.

### 5. Compile the tool-ready prompt

Write the prompt in this order:

1. Direct task and operation.
2. Primary subject, identity, pose, and action.
3. Environment and relationships between elements.
4. Composition, framing, viewpoint, and camera behavior.
5. Lighting, palette, materials, texture, and mood.
6. Exact typography, hierarchy, placement, and spelling.
7. Reference roles and target regions.
8. Preservation rules and exclusions.
9. Output requirements.

Use observable visual language. Replace empty adjectives such as “stunning” or “high quality” with concrete decisions the model can render.

### 6. Prepare the OpenRouter runtime

Read [references/openrouter-runtime.md](references/openrouter-runtime.md) before the first execution in a session or whenever configuration, model, parameters, or platform changes.

When `openai/gpt-image-2` is selected, read [references/gpt-image-2.md](references/gpt-image-2.md). Infer technical settings from intended use when the user leaves them open; do not force the user to specify API fields.

Resolve this skill's directory from the loaded `SKILL.md`; never assume the caller's current directory is the skill directory. Ensure Pillow is available. If `doctor` reports that it is missing, install the package dependency into the agent's active Python environment:

```text
python3 -m pip install -r <skill-dir>/requirements.txt
```

Obtain approval before a dependency installation when the host requires it. Then inspect the CLI with Python 3.9 or newer:

```text
python3 <skill-dir>/scripts/openrouter_image.py --help
```

If `<skill-dir>/.env` is absent, run `init`, then ask the user to edit that file locally. Do not continue until a key is configured. Run `doctor` before the first paid generation or after the configured model changes. `doctor` validates authentication and model discovery without generating an image.

If outbound network access or shell execution is unavailable, return the compiled prompt packet and state plainly that OpenRouter execution is unavailable. Do not fabricate a result.

### 7. Execute through OpenRouter

Write a temporary JSON request outside the installed skill. Include the compiled prompt, explicit output directory, exact count, supported rendering parameters, and required reference paths or HTTPS URLs. Keep the configured model implicit unless the user explicitly selects a different model.

Set `output_format` to the requested delivery format; default to `png`. The runner sends it to OpenRouter only when the selected model advertises support and otherwise converts the returned raster locally. Treat the manifest's delivered file as authoritative, not the provider's original media type.

Run:

```text
python3 <skill-dir>/scripts/openrouter_image.py generate --request <request.json>
```

Treat the JSON manifest on stdout as authoritative. Return only files listed in `files`. For edits, identify the target region in the prompt and state what must remain perceptually unchanged outside it. Local reference paths resolve relative to the request JSON; output paths resolve relative to the command's working directory.

For a requested batch:

- generate the exact requested count;
- let the runner split calls when the model does not support multi-image `n`;
- reuse one continuity brief across the batch;
- vary only intentional dimensions such as framing, color emphasis, or scene arrangement.

### 8. Verify and correct

Inspect every returned path whenever the environment supports image viewing. Read [references/quality-gates.md](references/quality-gates.md) before judging it.

Check semantic accuracy, hard constraints, reference fidelity, composition, exact text, and technical artifacts. If a mismatch is material and the selected model accepts image input, make one focused corrective request using the generated file as an input reference and preserving everything already correct. Do not enter an unbounded retry loop.

If inspection is unavailable, say that visual verification was not possible. Never imply verification occurred.

### 9. Return the result

Lead with the generated or edited asset. Briefly state the creative direction and any material limitation. Do not dump internal reasoning, raw chain-of-thought, or a fake workflow transcript.

Read [references/examples.md](references/examples.md) only when the request is ambiguous or requires an example for typography, reference preservation, compositing, or coordinated variants.

## Failure handling

- Diagnose whether failure came from missing input, configuration, unsupported model capability, OpenRouter rejection, network access, malformed output, or visual mismatch.
- Retry once only when a deterministic correction exists, such as fixing an argument name or narrowing an edit instruction.
- Do not automatically retry an ambiguous timed-out paid request; it may have reached the provider.
- Preserve the user's exact intent across retries.
- Report the real failure if execution still fails.
