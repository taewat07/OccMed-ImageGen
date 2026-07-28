# OccMed ImageGen

Open-source agent skills that help occupational medicine and occupational health professionals create clearer, safer visual communication with AI.

This repository focuses on reusable visual design and image-generation workflows for educational materials, workplace health communication, training, presentations, and research. It does not provide diagnosis, treatment, fitness-for-work decisions, or other clinical decision support.

## Included skills

| Skill | Purpose |
| --- | --- |
| [`extract-image-design`](skills/extract-image-design/) | Extracts a reusable, provider-neutral visual design system from reference images and stores it as structured JSON plus readable Markdown. Reference images remain local during extraction. |
| [`metaprompt-image-generation`](skills/metaprompt-image-generation/) | Turns a rough visual brief into a production-ready prompt, then generates or edits images through OpenRouter. The default model is `openai/gpt-image-2`. |

Each package contains its own `SKILL.md`, agent metadata, scripts, and supporting references. The image-generation package also includes an offline test suite.

## Install for Codex

Requirements:

- Python 3.9 or newer
- Git
- An OpenRouter API key for image generation only

Clone the repository and copy both packages into your Codex skills directory:

```bash
git clone https://github.com/taewat07/OccMed-ImageGen.git
mkdir -p ~/.codex/skills
cp -R OccMed-ImageGen/skills/extract-image-design ~/.codex/skills/
cp -R OccMed-ImageGen/skills/metaprompt-image-generation ~/.codex/skills/
```

Install the image runner dependency:

```bash
python3 -m pip install -r ~/.codex/skills/metaprompt-image-generation/requirements.txt
```

Initialize local OpenRouter configuration:

```bash
python3 ~/.codex/skills/metaprompt-image-generation/scripts/openrouter_image.py init
```

Open `~/.codex/skills/metaprompt-image-generation/.env` locally and add your key:

```dotenv
OPENROUTER_API_KEY=your_key_here
```

The `.env` file is ignored by Git. Never paste an API key into chat, a prompt, an issue, or a commit.

## Use

Extract a reusable design system from a local reference image:

```text
Use $extract-image-design to extract this image into a reusable design catalog entry.
```

Create an occupational health visual:

```text
Use $metaprompt-image-generation to create a 16:9 training image explaining correct hearing-protection use in a manufacturing workplace. Use no identifiable workers or company branding.
```

The generation skill asks for only the missing major specifications, compiles the prompt, runs the configured OpenRouter model, and checks the returned image when visual inspection is available.

## Privacy, clinical safety, and cost

- Never submit identifiable patient, employee, employer, or confidential workplace information.
- De-identify text, screenshots, forms, photographs, badges, faces, dates, facility names, and metadata before AI processing.
- `extract-image-design` analyzes accessible local images without uploading them. `metaprompt-image-generation` sends prompts and supplied reference images to OpenRouter and the selected model provider.
- Review generated visuals for factual accuracy, harmful stereotypes, unsafe work practices, invented labels, and misleading medical content before use.
- These skills are not medical devices and do not replace professional judgment, local regulations, workplace procedures, or clinical review.
- OpenRouter and its model providers may charge for requests and apply their own retention and privacy terms. Confirm those terms before processing workplace material.

## Development

Run the offline image-runner tests:

```bash
python3 -m unittest discover -s skills/metaprompt-image-generation/tests -p 'test_*.py'
```

Inspect either command-line interface:

```bash
python3 skills/extract-image-design/scripts/design_catalog.py --help
python3 skills/metaprompt-image-generation/scripts/openrouter_image.py --help
```

## License

Released under the [MIT License](LICENSE).
