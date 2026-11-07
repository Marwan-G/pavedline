---
name: diagram
description: How to write, validate and render Graphviz .dot diagrams in a Pavedline product repository, in the shared style. Use whenever a step needs a .dot file (landscape, architecture, ERD, plan) or a diagram must be updated.
---

# diagram

GitHub does not render `.dot`, so every `.dot` is committed next to its rendered `.svg`.

## When a .dot is required

- Every folder that holds architecture has an `ARCHITECTURE.dot` (repository root, `infra/`, `infra/k8s/`, each service, `docs/architecture/`).
- `docs/data/erd.dot` for the data model.
- `docs/business/landscape.dot` for the market (step 1).
- Every plan in `docs/plans/` has its own `.dot`.
- A change under a folder that has an `ARCHITECTURE.dot` updates that `.dot`, or the pull request states `diagram unchanged: <reason>`.

## Style (keep it the same everywhere)

- Boxes: `shape=box, style="rounded,filled"`. Font: Helvetica. Edge labels short.
- One colour per area (clients, backend, data, platform), as a filled cluster with a lighter box colour inside. Copy the palette from `ARCHITECTURE.dot` if the repository has one.
- Cross-cutting rails (auth, observability, secrets) are notes, not boxes wired to everything.
- Left-to-right (`rankdir=LR`) unless the diagram is a timeline. A title label at the top. No more than about 25 nodes: split the diagram instead.
- A comment at the top says what the file is the source of.

## Validate, then render

Run both after every edit:

```
dot -Tcanon -o /dev/null <file>.dot
dot -Tsvg <file>.dot -o <file>.svg
```

`-Tcanon` exits non-zero on a syntax error; fix the error before rendering. Name the SVG after the `.dot` (drop `.dot`, add `.svg`). Commit both files together. Never edit the SVG by hand. If `dot` is missing, run `/pavedline:doctor` and ask the user to install Graphviz; do not write an SVG yourself.

(A later Pavedline release adds a script that does this and a CI drift check. Until then, the two commands above are the whole procedure.)
