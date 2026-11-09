{{/* Name of a workload's resources: <release>-<workload>, at most 63 characters. */}}
{{- define "base.fullname" -}}
{{- printf "%s-%s" .root.Release.Name .name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "base.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end -}}

{{- define "base.labels" -}}
{{ include "base.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .root.Chart.Name .root.Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/* image: repository + tag, or repository@digest. One of tag or digest is required. */}}
{{- define "base.image" -}}
{{- $img := required (printf "workloads.%s.image is required" .name) .w.image -}}
{{- $repo := required (printf "workloads.%s.image.repository is required" .name) $img.repository -}}
{{- if $img.digest -}}
{{- printf "%s@%s" $repo $img.digest -}}
{{- else -}}
{{- printf "%s:%s" $repo (required (printf "workloads.%s.image.tag (or digest) is required" .name) $img.tag) -}}
{{- end -}}
{{- end -}}

{{/* Pod security context, shared by the Deployment and the migration Job. */}}
{{- define "base.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .w.runAsUser | default 10001 }}
runAsGroup: {{ .w.runAsUser | default 10001 }}
fsGroup: {{ .w.runAsUser | default 10001 }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "base.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
runAsNonRoot: true
capabilities:
  drop:
    - ALL
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "base.probe" -}}
httpGet:
  path: {{ .p.path | default "/" }}
  port: http
initialDelaySeconds: {{ .p.initialDelaySeconds | default 5 }}
periodSeconds: {{ .p.periodSeconds | default 10 }}
timeoutSeconds: {{ .p.timeoutSeconds | default 2 }}
failureThreshold: {{ .p.failureThreshold | default 3 }}
{{- end -}}

{{- define "base.env" -}}
{{- range $k, $v := .w.env }}
- name: {{ $k }}
  value: {{ $v | quote }}
{{- end }}
{{- range .w.secretEnv }}
- name: {{ .name }}
  valueFrom:
    secretKeyRef:
      name: {{ .secretName }}
      key: {{ .key }}
{{- end }}
{{- end -}}
