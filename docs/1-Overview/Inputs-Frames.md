# Inputs: Frames

Frames are the **strict**, **flat JSON** input format used by SemantiK Architect for stable generation. In the system’s dual-path design, Frames correspond to the **“Strict Path”** (validated internal frame objects such as `BioFrame`) intended for production reliability.

---

## What a “Frame” is

A Frame is a compact, structured way to express **meaning/intention** without tying it to any particular language’s surface grammar.

Think of it as: **“what you want to say”**, expressed with a small set of named fields that the renderer can reliably turn into text.

---

## How SemantiK Architect interprets Frames

- A Frame is identified by a **`frame_type`** field (e.g., `"bio"`).
- The remaining fields are the **arguments/slots** needed to express that meaning (e.g., `name`, `profession`, etc.).
- The request is routed to the corresponding strict handler and **validated** before generation.

---

## Example: BioFrame (illustrative)

This example shows the “shape” of a typical Frame request:

```json
{
  "frame_type": "bio",
  "name": "Alan Turing",
  "profession": "computer scientist",
  "nationality": "british",
  "gender": "m"
}
````

(Other frame types will define different required/optional slots.)

---

## When to use Frames vs Ninai

Use **Frames** when you want:

* a **simple, stable contract** for upstream systems you control,
* **strict validation** and predictable behavior,
* an intentionally “flat” meaning form that is easy to author and debug.

Use **Ninai** when you want:

* a **recursive object-tree** meaning representation (more expressive),
* a format that can be **adapted into internal frames** through the Ninai bridge.

See also:

* [[Inputs: Ninai|Inputs-Ninai]]
* [[API Overview|API-Overview]]

