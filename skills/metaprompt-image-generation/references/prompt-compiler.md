# Prompt Compiler

Use this reference to convert user language into a provider-neutral image prompt without losing constraints.

## Visual intent contract

Normalize the request into this internal structure. Omit empty fields; do not expose it unless useful.

```yaml
operation: generate | edit | composite | variation
goal: communication outcome
audience: intended viewer
must_show:
  - required subject, object, action, symbol, or exact text
must_preserve:
  - identity, geometry, logo, pose, layout, or untouched region
may_change:
  - decisions delegated to the agent
subject:
  identity: defining visual traits or reference assignment
  pose_action: observable posture, expression, and movement
scene:
  environment: place, time, atmosphere
  relationships: spatial and narrative relationships
composition:
  hierarchy: primary, secondary, background
  framing: close-up, medium, wide, negative space
  viewpoint: eye level, low angle, overhead, isometric
camera: lens behavior, depth of field, motion treatment
lighting: source, direction, softness, contrast, practical lights
palette: dominant, supporting, and accent colors
materials: surfaces, texture, finish, physical behavior
typography:
  exact_text: verbatim copy
  hierarchy: headline, subhead, supporting copy
  placement: region, alignment, scale, clear space
references:
  - source: stable label or path
    role: identity | object | layout | style | background
    target: subject or region affected
exclusions:
  - forbidden element, mutation, artifact, or drift
output:
  count: exact number
  aspect_ratio: requested or agent-selected ratio
  resolution: only when supported or required
  format: only when supported or required
```

## Compilation rules

1. Preserve the hierarchy: explicit user constraints outrank inferred art direction; art direction outranks generic aesthetic defaults.
2. Resolve ambiguity into one visual decision unless missing information blocks execution.
3. Describe visible evidence. “Premium” becomes restrained hierarchy, deliberate negative space, controlled highlights, refined material finish, and limited accent color.
4. Describe relationships, not inventories. State where objects sit, which way subjects face, what overlaps, and where attention should land.
5. Keep each reference's role narrow and explicit. A face reference supplies identity; it does not silently control wardrobe, layout, or lighting.
6. Place preservation language near the referenced content and repeat only critical constraints at the end.
7. Put exact display text in quotation marks. Specify capitalization, line breaks, hierarchy, placement, and a prohibition on extra text.
8. Do not use artist names or copyrighted franchise shorthand when concrete visual attributes can express the direction.

## Creative direction brief

Before compiling, form this compact internal brief:

```text
Intent: [what the image must communicate]
Focus: [primary subject and hierarchy]
Scene: [environment and key relationships]
Composition: [framing, viewpoint, negative space]
Look: [lighting, palette, materials, mood]
Type: [exact copy, hierarchy, placement]
Continuity: [what remains stable across edits or variants]
```

Every line must affect either the prompt or a tool argument. Delete decorative commentary.

## Compiled prompt template

```text
[Create/Edit/Composite] [deliverable and purpose].

Primary subject: [identity, defining traits, pose, expression, action].
Scene: [environment, time, atmosphere, spatial relationships].
Composition: [hierarchy, framing, viewpoint, lens behavior, negative space].
Lighting and color: [sources, direction, contrast, palette].
Materials and finish: [specific surfaces and texture behavior].
Typography: Render exactly "[copy]" with [case/line breaks], [hierarchy], at [placement]. Add no other text.
References: Use [source] only for [role] on [target].
Preserve: [identity, geometry, layout, or untouched regions].
Exclude: [unwanted elements, mutations, drift, artifacts].
Output: [count, ratio, and deliverable constraints not represented by tool fields].
```

Remove irrelevant lines. Favor one dense, coherent prompt over fragmented prompt fragments.

## Operation-specific instructions

### Generate

Anchor the prompt around a single focal story. Define enough environment to make the composition deterministic without filling every pixel with detail.

### Edit

State the change first, then the preservation boundary:

```text
Change only [target region or object] from [current state] to [desired state]. Preserve [identity, pose, lighting, perspective, text, and all unaffected regions]. Match existing grain, shadow direction, color response, and edge detail.
```

### Composite

Assign every source a role and reconcile perspective, scale, occlusion, lighting direction, shadow softness, color temperature, and grain. Never say merely “combine these images.”

### Variation

Define a continuity lock and a controlled variation axis:

```text
Keep [identity, brand system, palette, lighting logic, typography, product geometry] consistent. Vary only [framing, viewpoint, scene arrangement, or accent emphasis].
```

## Tool adaptation

- Dedicated tool fields beat prose for count, size, ratio, source image, mask, and seed.
- The tool schema is authoritative. Unknown parameters are errors, not creative freedom.
- If the model supports masks, describe the same target boundary in both the mask and prompt.
- If the model lacks negative prompts, state exclusions as direct imperatives: “Do not add…”, “Keep free of…”, “Preserve…”.
- If exact typography fails, use one corrective edit focused only on the text region while preserving the approved image.
