{{/*
base.render: the single entry point. An app chart's templates/ holds one line: {{ include "base.render" . }}
Reads .Values.workloads (a map: workload name -> settings), .Values.priorityClassName, .Values.gateway.
*/}}
{{- define "base.render" -}}
{{- $root := . -}}
{{- $_ := required "priorityClassName is required" .Values.priorityClassName -}}
{{- range $name, $w := (required "workloads is required" .Values.workloads) }}
{{- $ctx := dict "root" $root "name" $name "w" $w "fullname" (include "base.fullname" (dict "root" $root "name" $name)) }}
---
{{ include "base.serviceAccount" $ctx }}
---
{{ include "base.deployment" $ctx }}
---
{{ include "base.service" $ctx }}
---
{{ include "base.pdb" $ctx }}
---
{{ include "base.networkPolicy" $ctx }}
{{- if ($w.autoscaling).enabled }}
---
{{ include "base.hpa" $ctx }}
{{- end }}
{{- if ($w.route).enabled }}
---
{{ include "base.route" $ctx }}
{{- end }}
{{- if ($w.migrations).enabled }}
{{- $mctx := dict "root" $root "name" (printf "%s-migrate" $name) "w" $w "fullname" $ctx.fullname "suffix" "-migrate" "hook" true }}
---
{{ include "base.serviceAccount" $mctx }}
---
{{ include "base.networkPolicy" $mctx }}
---
{{ include "base.migrationJob" $mctx }}
{{- end }}
{{- end }}
{{- end -}}
