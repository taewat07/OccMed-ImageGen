---
name: extract-image-design
description: Extract reusable visual design systems from one or more reference images into structured, provider-neutral JSON and a human-readable DESIGN.md, then organize entries in a portable, searchable catalog. Use when Codex needs to analyze an image's composition, hierarchy, geometry, palette, typography, linework, texture, lighting, medium, motifs, or mood; turn visual references into reusable image-generation prompts; document an art direction or visual style; compare a coordinated reference set; or initialize, validate, render, and reindex a design catalog.
---

# Extract Image Design

Turn reference images into evidence-based, reusable design specifications. Keep `design.json` canonical; generate `DESIGN.md`, `catalog.json`, and `CATALOG.md` with the bundled script.

## Operating rules

- Analyze only images available to the current environment. Never upload a reference during extraction.
- Copy every reference into the catalog entry so the entry remains portable.
- Separate observation from inference. Describe visible evidence before assigning style, era, medium, font, or production labels.
- Separate transferable design rules from depicted subjects, words, logos, signatures, and one-off layout content.
- Never invent artist attribution, font identity, production method, exact dimensions, or exact color values. Use `unknown` or qualitative language when evidence is insufficient.
- Preserve uncertainty with `confidence` and concrete `evidence`; do not inflate weak guesses into facts.
- Describe visual characteristics rather than using a living artist's name as a generation shortcut.
- Do not manually edit generated Markdown or catalog indexes.
- Keep prompts provider-neutral. Hand generation work to a dedicated image-generation skill after extraction.

## Resolve paths

Resolve `<skill-dir>` from this loaded `SKILL.md`; do not assume the caller's current directory. Default `<catalog-dir>` to `./design-catalog` unless the user supplies another location.

Use:

```text
python3 <skill-dir>/scripts/design_catalog.py --help
```

The script uses only the Python standard library.

## Extraction workflow

### 1. Initialize or inspect the catalog

If `<catalog-dir>` does not exist, initialize it:

```text
python3 <skill-dir>/scripts/design_catalog.py init <catalog-dir>
```

If it exists, validate it before adding content:

```text
python3 <skill-dir>/scripts/design_catalog.py validate <catalog-dir>
```

Stop on validation errors. Repair canonical JSON or missing source files before continuing; never hide drift by editing generated Markdown.

### 2. Create the entry

Choose a stable lowercase hyphenated slug that describes the design system rather than only the depicted subject. Create one entry from all coordinated references:

```text
python3 <skill-dir>/scripts/design_catalog.py new <catalog-dir> <slug> --source <image> [--source <image> ...]
```

The command copies references, records hashes, creates a draft `design.json`, and reindexes the catalog. A slug collision is an error; update the existing entry deliberately instead of creating a near-duplicate.

### 3. Inspect every copied reference

Use the environment's image-viewing capability on each file under `entries/<slug>/sources/`. For multiple images, first analyze each image independently, then record only shared traits as system-level invariants. Put image-specific differences in flexible characteristics or content-specific elements.

Read [references/extraction-rubric.md](references/extraction-rubric.md) before filling the entry. Read [references/design.schema.json](references/design.schema.json) when field shape or allowed values are unclear.

### 4. Fill canonical JSON

Edit only `entries/<slug>/design.json`.

- Keep `schema_version` at `1.0`.
- Preserve copied `sources` paths, sizes, and SHA-256 values.
- Replace the generated title and draft summary with meaningful language.
- Populate every observation group that is visually applicable.
- Set `inferred: false` for directly visible claims and `true` for interpretive labels.
- Cite visible evidence such as placement, edge behavior, repeated shapes, measured proportions, or sampled pixels.
- Put reusable rules under `transferable_design_system`.
- Put depicted people, objects, wording, brands, and signatures under `content_specific_elements`.
- Make `prompt_packet.positive_prompt` usable with a new subject. Keep source-specific content out unless it is an essential reusable motif.
- Use descriptive exclusions in `negative_prompt`; do not rely on generator-specific syntax.
- Update `provenance.updated_at` in UTC and set `identity.status` to `complete` only after the entry is fully analyzed.

### 5. Render and index

Validate and render the entry, then regenerate catalog indexes:

```text
python3 <skill-dir>/scripts/design_catalog.py render <catalog-dir>/entries/<slug>
python3 <skill-dir>/scripts/design_catalog.py reindex <catalog-dir>
python3 <skill-dir>/scripts/design_catalog.py validate <catalog-dir>
```

Treat any stale-file report as a failed extraction. `DESIGN.md` must contain the exact provider-neutral prompt packet from `design.json`.

### 6. Return the artifact

Return links to `DESIGN.md` and `design.json`. State the catalog entry slug, number of references, and any material uncertainty. Do not claim a font, artist, exact palette, or process was identified unless the evidence supports it.

## Catalog maintenance

- Run `render` after every canonical entry edit.
- Run `reindex` after adding, removing, or changing entry identity or taxonomy.
- Run `validate` before handing off or committing a catalog.
- Keep entries flat under `entries/`; organize them with `taxonomy.tags` and `taxonomy.collections` so paths remain stable.
- Preserve existing `created_at`; advance `updated_at` only when canonical content changes.

## Failure handling

- Missing or unreadable reference: stop and request an accessible local image.
- Unsupported or non-image source: reject it; do not copy arbitrary files into `sources/`.
- Conflicting references: keep only shared rules as invariants and record the conflict as a flexible characteristic.
- Illegible text: record visible typographic behavior and mark transcription uncertainty; never guess wording.
- Invalid JSON or schema: fix `design.json`, rerun `render`, then rerun `validate`.
- Hash mismatch: determine whether the source was intentionally replaced. If intentional, create a fresh entry or update its source metadata explicitly before analysis.
