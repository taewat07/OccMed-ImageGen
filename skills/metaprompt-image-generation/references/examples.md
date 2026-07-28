# Examples

These examples demonstrate the transformation from intent to executable prompt. Adapt their structure, never their visual content by default.

## Vague request becomes concrete art direction

User intent:

```text
Make a launch poster for a privacy-first AI notebook. It should feel premium.
```

Compiled prompt:

```text
Create a vertical product-launch poster communicating private, local intelligence. Center a slim graphite notebook on a dark mineral desk, viewed from a restrained three-quarter angle. A soft pool of warm light falls only across the notebook while the surrounding space remains calm and dark, suggesting protected focus. Use a disciplined editorial hierarchy, generous negative space above the product, charcoal and warm-gray surfaces, one muted electric-blue status light, fine paper texture, and controlled satin reflections. No cloud icons, padlock clichés, people, decorative circuitry, or invented text. Output one vertical 4:5 poster.
```

## Reference-preserving edit

User intent:

```text
Remove the coffee cup and make the wall warmer. Do not change the person or poster text.
```

Compiled prompt:

```text
Edit the supplied image. Remove only the coffee cup and reconstruct the desk surface beneath it with matching wood grain, perspective, shadow softness, sharpness, and noise. Shift only the wall paint toward a restrained warm clay tone while preserving its existing light gradient and texture. Preserve the person's identity, face, hair, pose, clothing, hands, body proportions, lighting, and edges exactly. Preserve all poster geometry and render its text pixel-consistently with the source. Do not change the camera, crop, desk objects, or any other region.
```

## Multi-reference composite

Reference assignments:

- Reference 1: person's identity and clothing.
- Reference 2: product geometry and logo.
- Reference 3: room layout only.

Compiled prompt:

```text
Create one coherent editorial photograph using the supplied references. Place the person from Reference 1 at the left side of the desk in the room layout from Reference 3, naturally holding the product from Reference 2 at chest height. Preserve the person's facial identity, hair, skin tone, clothing, and body proportions. Preserve the product's dimensions, controls, material seams, and logo geometry. Use Reference 3 only for architecture and furniture placement; do not copy its people or wall art. Reconcile all sources to the room's eye-level perspective, late-afternoon window light from camera right, soft contact shadows, warm-neutral color temperature, and fine photographic grain. Keep fingers naturally wrapped around the product without covering the logo. Add no text or extra objects.
```

## Coordinated variants

User intent:

```text
Create three campaign images that feel like one set.
```

Continuity lock:

```text
Across all three images, preserve subject identity, product geometry, warm-white background, cobalt accent, soft upper-left key light, medium contrast, and the same editorial type system. Produce exactly three images. Vary only framing and scene arrangement: one centered hero, one close detail, and one contextual wide scene. Keep logo size, headline placement, color response, and surface finish consistent.
```
