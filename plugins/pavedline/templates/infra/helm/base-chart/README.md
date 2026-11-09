# base-chart (library chart)

An application chart depends on this chart and has one template file, `templates/all.yaml`, containing a single `include` of the
`base.render` template with the root context (see `skills/helm-base-chart`).

Everything is driven by the app chart's values (see `skills/helm-base-chart`).
`app-values.schema.json` is the values schema. A library chart's own `values.schema.json` would validate the
wrong values, so each app chart copies this file to its own `values.schema.json` unchanged (a test checks the
copy is identical).
