# OccMed ImageGen

Open-source agent skills that help occupational medicine and occupational health professionals create clearer, safer visual communication with AI.

This repository focuses on reusable visual design and image-generation workflows for educational materials, workplace health communication, training, presentations, and research. It does not provide diagnosis, treatment, fitness-for-work decisions, or other clinical decision support.

## How meta-prompting works

```mermaid
flowchart LR
    A["👤 Your Idea"] --> B["🤖 AI Agent"]
    B -- "Meta-Prompt" --> C["🖼️ Generate Image"]
```

## Example results

The same hearing-protection message can take very different visual directions. The first poster uses generic GPT Image 2 styling; the others use design systems extracted from visual references.

| Generic GPT Image 2 | Design-guided: pop-art graffiti | Design-guided: children's storybook |
| :---: | :---: | :---: |
| [![Generic GPT Image 2 hearing-protection poster](examples/generic-gpt-image-2-hearing-protection-poster.webp)](examples/generic-gpt-image-2-hearing-protection-poster.webp) | [![Pop-art graffiti design-guided hearing-protection poster](examples/pop-art-graffiti-design-guided-hearing-protection-poster.webp)](examples/pop-art-graffiti-design-guided-hearing-protection-poster.webp) | [![Children's storybook design-guided hearing-protection poster](examples/childrens-storybook-design-guided-hearing-protection-poster.webp)](examples/childrens-storybook-design-guided-hearing-protection-poster.webp) |
| **About ฿1.45** | **About ฿1.45** | **About ฿1.45** |

> These are illustrative AI-generated outputs. Verify all medical, safety, and regulatory content before use.

All three examples used `openai/gpt-image-2`, medium quality, a `9:16` aspect ratio, and one output. The estimated price is approximately US$0.043, or ฿1.45, per image. Actual OpenRouter charges can vary slightly with prompt length, reference-image inputs, model pricing, and exchange rates.

## Pay only for the images you create

This workflow does not require a paid ChatGPT subscription. OpenRouter bills each API generation separately, while ChatGPT subscriptions bundle image creation with many other ChatGPT features.

| ChatGPT plan | Published US price | Approximate Thai-baht price per month | Published image access | Same spend at ฿1.45 per image |
| --- | ---: | ---: | --- | ---: |
| Free | $0 | ฿0 | Limited and slower | — |
| Go | $8/month | About ฿269/month | More than Free; no fixed public image quota | About 185 images |
| Plus | $20/month | About ฿673/month | More complex and accurate creation; limits apply | About 464 images |
| Pro | $200/month | About ฿6,727/month | Unlimited and faster, subject to abuse guardrails | About 4,639 images |

Prices are a simple cost comparison, not equivalent products: ChatGPT subscriptions include many non-image features. Thai-baht figures use the Bank of Thailand's 24 July 2026 USD transfer rate of ฿33.6367 per US$1 and exclude taxes, card fees, and regional pricing. See [OpenAI's consumer-plan announcement](https://openai.com/index/introducing-chatgpt-go/), [current ChatGPT plan details](https://chatgpt.com/pricing/), [OpenAI image pricing](https://developers.openai.com/api/docs/pricing#image-generation), and [Bank of Thailand exchange rates](https://www.bot.or.th/en/statistics/financial-institutions/exchange-rate.html).

## What you can customize

The agent turns a short idea into a detailed production prompt, while keeping the important creative and delivery controls explicit:

| Control | What you can specify |
| --- | --- |
| Aspect ratio | `1:1`, `3:2`, `2:3`, `4:3`, `3:4`, `16:9`, `9:16`, `21:9`, or automatic |
| Image size | Choose the intended layout and aspect ratio; the model selects native pixels. These examples are 864×1536. Exact delivery dimensions can be produced with a local resize or crop. |
| Quality and cost | `low`, `medium`, `high`, or automatic |
| Visual direction | Subject, action, composition, art style, color palette, lighting, viewpoint, mood, and exclusions |
| Visible text | Exact headline, labels, language, hierarchy, and placement |
| Design references | Use up to 16 images to guide identity, product geometry, composition, or style |
| Batch size | Generate 1–10 images in one request |
| Delivery | PNG or JPEG, JPEG compression, and automatic or opaque background |

For example:

```text
Create a 9:16 hearing-protection poster for factory workers. Use medium quality,
a friendly children's-storybook style, a warm color palette, and this exact
headline: "Protect Your Hearing Every Day". Show correct earmuff placement,
avoid identifiable people and company branding, and deliver one PNG image.
```

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
