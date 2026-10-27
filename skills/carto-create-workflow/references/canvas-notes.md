# Canvas notes and section containers

`type: "note"` nodes are markdown cards pinned to the Workflows canvas. They emit no SQL and
have no inputs or edges — they exist purely to document the DAG for whoever opens it next.

Two ways to use them:

- **Caption** — a small card placed near a step, explaining it.
- **Section container** — a card sized to *enclose* a group of nodes. Notes render at
  `zIndex: -1`, so an enclosing note reads as a labelled section behind the DAG. This is how
  you turn a 20-node pipeline into four or five named stages.

There is **no `section` node type in practice.** `carto workflows schema node` lists `section`
in its `type` enum, but no live workflow or reference bundle uses one. Notes are the mechanism.

> The CLI does not serve a schema for notes — `carto workflows schema node.note` returns
> *Unknown section*, and `schema node`'s `data` properties do not include the note-specific
> fields. Hence this reference.

## Wire shape

```jsonc
{
  "id": "<uuid>",
  "type": "note",
  "zIndex": -1,                       // keeps the card BEHIND the DAG. Omit and it covers nodes.
  "width": 544,                       // = data.width  + 160   (see geometry below)
  "height": 400,                      // = data.height + 128
  "position": { "x": -24, "y": -176 },
  "positionAbsolute": { "x": -24, "y": -176 },
  "selected": false,
  "dragging": false,
  "data": {
    "name": "Note",
    "color": "#F6CF71",               // card fill
    "genAi": false,
    "label": "",                      // leave empty — the caption comes from frontmatter
    "width": 384,                     // ← THE VISIBLE BOX
    "height": 272,                    // ← THE VISIBLE BOX
    "inputs": [],
    "markdown": "---\nlabel: 2 · Demand per cell\n---\n## Heading\nBody text…"
  }
}
```

## Geometry: `data.*` is the visible box

**The canvas draws the card at `data.width` × `data.height`.** The node-level `width` /
`height` are React Flow bookkeeping and are always `data + 160` / `data + 128`.

This is the single easiest thing to get wrong, because a lone example is consistent with either
reading. Size `node.*` to your intended span and derive `data.*` by *subtracting* the chrome and
every card renders **160 px too narrow and 128 px too short** — which looks fine in isolation
and silently drops the rightmost and bottom-most members out of a section container.

So, to make a container span a bounding box of `w × h`:

```
data.width  = w          node.width  = w + 160
data.height = h          node.height = h + 128
position    = (x0, y0)   # top-left of the intended span
```

Positions snap to a **16 px grid**. Positions never affect execution.

## Building a section container

Derive the geometry from the members' bounding box rather than hand-placing it, so the container
stays correct when the pipeline moves:

```python
xs0 = min(n["position"]["x"] for n in members) - pad_l
xs1 = max(n["position"]["x"] + n["width"] for n in members) + pad_r
ys0 = min(n["position"]["y"] for n in members) - pad_t
ys1 = max(n["position"]["y"] + n["height"] for n in members) + pad_b
```

Node dimensions for the bounding box: **source nodes 192 × 64**, **generic components 64 × 64**.

**`pad_t` matters most.** Note text renders from the top of the card and flows down, and nodes
sit on top of it, so anything past the header area is hidden behind the cards. Around **176 px**
of top padding clears the label chip, an `##` heading and a line or two. Side and bottom padding
of 24–40 px is plenty.

Keep the body to a heading plus one or two short lines. A section container is orientation, not
documentation — the detail belongs in SQL comments or the repo.

## Two layout pitfalls

**Containers must not overlap.** Assert it; do not eyeball it. There is no way to screenshot a
workflow canvas, so a bad layout is invisible until someone opens the DAG. A 176 px header needs
roughly `pad_t + pad_b + node_height` of vertical clearance between stacked rows — if the source
rows are 144 px apart, the boxes will collide. Scaling every node's `y` by an integer factor is a
safe fix: it is linear, so a join positioned on the midline of two source rows stays on the
midline.

**A group cannot mix a source at `x = 0` with nodes on the shared pipeline row.** Two such groups
have bounding boxes that overlap *by construction*, whatever the padding — both span from `x = 0`
to somewhere along the same row. Either give the sources their own container, or group strictly by
pipeline segment.

## Verification

Notes are inert, so prove they stayed inert and that the geometry is right:

```bash
# 1. Notes must not change the generated SQL. Count must match before and after.
carto workflows to-sql --file wf.json --connection <conn> | grep -c '===='
```

```python
# 2. Every member must sit inside its container's VISIBLE box — data.*, not node.*.
#    Measuring node.* here is the trap: it agrees with the inverted-geometry bug.
bx1 = box["position"]["x"] + box["data"]["width"]
by1 = box["position"]["y"] + box["data"]["height"]
```

`validate` and `verify-remote` pass regardless of note geometry — neither checks layout.
