# Image Quality Gates

Inspect the actual output when possible. Judge against the visual intent contract, not against personal taste added after generation.

## Gate 1: Intent

- Does the image communicate the requested idea at first glance?
- Is the intended subject unmistakably primary?
- Does the emotional tone match the use case and audience?

## Gate 2: Hard constraints

- Are all required subjects, objects, actions, symbols, and brand elements present?
- Are requested count, orientation, aspect ratio, and layout respected?
- Is every explicit exclusion respected?

Any failed hard constraint is a material mismatch.

## Gate 3: Reference fidelity

- Is identity stable: facial structure, age, skin tone, hair, and distinctive features?
- Is product or logo geometry preserved?
- Are pose, layout, background, and untouched regions preserved where required?
- Did a style reference leak unwanted people, objects, logos, or composition into the result?

Identity drift or preservation-boundary damage is material.

## Gate 4: Composition and visual logic

- Is hierarchy clear at the intended viewing size?
- Are perspective, scale, occlusion, reflections, and shadows internally consistent?
- Is negative space usable for its intended purpose?
- Do composite sources appear to share one physical scene?

## Gate 5: Typography

- Does text match the requested spelling, capitalization, punctuation, and line breaks exactly?
- Is hierarchy and placement correct?
- Is the copy legible and free of duplicated or invented characters?
- Is there any accidental extra text?

Incorrect required copy is a material mismatch.

## Gate 6: Technical integrity

- Check hands, eyes, teeth, repeated structures, object boundaries, and fine geometry.
- Check halos, seams, warped logos, broken reflections, inconsistent grain, and compression artifacts.
- Confirm edits blend with local sharpness, noise, color response, and depth of field.

## Correction policy

Make one corrective pass only when a mismatch is material and an edit-capable tool is available.

Write the correction as a surgical delta:

```text
Preserve everything currently correct, including [approved elements]. Change only [defect and target region]. The corrected result must [measurable requirement]. Do not alter [preservation boundary].
```

Do not regenerate the entire concept to fix a local defect. Do not retry for harmless taste differences that satisfy the contract. If correction still fails, return the best real result and identify the unresolved limitation.
