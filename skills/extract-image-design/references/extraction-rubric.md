# Image Design Extraction Rubric

Use this rubric while inspecting copied reference images. Record only categories supported by visible evidence.

## Evidence discipline

For every observation, write:

- `statement`: one atomic visual claim;
- `evidence`: concrete visible cues supporting it;
- `confidence`: `high`, `medium`, or `low`;
- `inferred`: `false` for direct observation, `true` for interpretation.

Direct observation: “The focal object occupies the central third and overlaps the horizon.”

Inference: “The limited colors and dot texture suggest a screen-print influence.”

Do not identify an artist, font family, historical era, material, or production method from resemblance alone. Phrase uncertain labels as influence or appearance and lower confidence.

## Analysis pass

1. **Composition** — orientation, aspect ratio, framing, grid, balance, negative space, cropping, viewpoint, depth layers, and repeated alignment.
2. **Visual hierarchy** — focal order, scale contrast, salience, reading path, grouping, overlap, and foreground/background separation.
3. **Geometry** — dominant primitives, contour behavior, proportions, symmetry, corner language, density, and spacing rhythm.
4. **Color** — dominant and accent roles, temperature, saturation, value range, contrast relationships, and approximate swatches. Use exact hex only when pixels were sampled; otherwise mark values as approximate.
5. **Typography** — case, weight appearance, width, contrast, spacing, alignment, hierarchy, placement, and integration with imagery. Name a font only with independent evidence.
6. **Linework** — contour weight, consistency, taper, roughness, edge sharpness, internal detail, and outline/fill relationship.
7. **Texture** — grain, halftone, noise, paper, brush, gloss, wear, gradients, and whether texture is global or localized.
8. **Lighting** — direction, hardness, number of apparent sources, contrast, shadow behavior, rim light, glow, atmospheric effects, and color temperature.
9. **Medium** — visible rendering behavior such as vector-flat, photographic, painterly, 3D-rendered, collage, or print-like. Treat the physical process as inferred unless documented.
10. **Motifs** — recurring shapes, marks, props, framing devices, decorative vocabulary, and symbols. Keep branded or narrative motifs content-specific unless the user owns and wants them preserved.
11. **Mood** — observable emotional cues tied to palette, lighting, pose, density, scale, and rhythm rather than unsupported adjectives.

## Transfer test

A rule is transferable only if it still makes sense after replacing the depicted subject.

- Put stable composition, palette relationships, edge behavior, texture treatment, hierarchy, and rendering rules in `transferable_design_system`.
- Put characters, products, scenery, exact words, logos, signatures, and incidental props in `content_specific_elements`.
- Put traits shared across all references in `invariants`.
- Put legitimate variation across references in `flexible_traits`.
- Put common failure modes and features that would break the style in `avoid`.

## Prompt packet quality gate

The positive prompt must specify a new subject through a named variable, then express observable design behavior. It must not simply repeat style labels.

The packet must include:

- a short creative `direction`;
- one provider-neutral `positive_prompt`;
- one plain-language `negative_prompt`;
- replaceable `variables`, including at least `subject`;
- `essential_invariants` copied from the reusable system;
- `flexible_characteristics` that may vary without losing identity.

Before completion, verify that someone could substitute the `subject` variable without accidentally recreating source-specific people, products, wording, logos, or signatures.
