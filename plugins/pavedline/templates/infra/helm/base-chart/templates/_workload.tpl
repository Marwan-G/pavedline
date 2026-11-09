{{- define "base.serviceAccount" -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .fullname }}{{ .suffix | default "" }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
  {{- if .hook }}
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
    argocd.argoproj.io/sync-wave: "-2"
  {{- end }}
automountServiceAccountToken: false
{{- end -}}

{{- define "base.deployment" -}}
{{- $w := .w -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .fullname }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
spec:
  {{- if not (($w.autoscaling).enabled) }}
  replicas: {{ $w.replicas | default 1 }}
  {{- end }}
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      {{- include "base.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "base.labels" . | nindent 8 }}
      {{- with $w.podAnnotations }}
      annotations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
    spec:
      serviceAccountName: {{ .fullname }}
      automountServiceAccountToken: false
      priorityClassName: {{ required "priorityClassName is required" .root.Values.priorityClassName }}
      securityContext:
        {{- include "base.podSecurityContext" . | nindent 8 }}
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              {{- include "base.selectorLabels" . | nindent 14 }}
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              {{- include "base.selectorLabels" . | nindent 14 }}
      containers:
        - name: {{ .name }}
          image: {{ include "base.image" . | quote }}
          imagePullPolicy: {{ ($w.image).pullPolicy | default "IfNotPresent" }}
          {{- with $w.command }}
          command:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with $w.args }}
          args:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          ports:
            - name: http
              containerPort: {{ $w.port | default 8000 }}
              protocol: TCP
          {{- $env := include "base.env" . }}
          {{- if $env }}
          env:
            {{- $env | nindent 12 }}
          {{- end }}
          {{- with $w.envFromSecrets }}
          envFrom:
            {{- range . }}
            - secretRef:
                name: {{ . }}
            {{- end }}
          {{- end }}
          livenessProbe:
            {{- include "base.probe" (dict "p" (required "probes.liveness is required" ($w.probes).liveness)) | nindent 12 }}
          readinessProbe:
            {{- include "base.probe" (dict "p" (required "probes.readiness is required" ($w.probes).readiness)) | nindent 12 }}
          resources:
            {{- toYaml (required "resources is required" $w.resources) | nindent 12 }}
          securityContext:
            {{- include "base.containerSecurityContext" . | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            {{- range .w.extraEmptyDirs }}
            - name: {{ .name }}
              mountPath: {{ .mountPath }}
            {{- end }}
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: {{ $w.tmpSizeLimit | default "64Mi" }}
        {{- range $w.extraEmptyDirs }}
        - name: {{ .name }}
          emptyDir:
            sizeLimit: {{ .sizeLimit | default "64Mi" }}
        {{- end }}
{{- end -}}

{{- define "base.service" -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ .fullname }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    {{- include "base.selectorLabels" . | nindent 4 }}
  ports:
    - name: http
      port: {{ .w.servicePort | default 80 }}
      targetPort: http
      protocol: TCP
{{- end -}}

{{- define "base.pdb" -}}
{{- $pdb := .w.pdb | default dict -}}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ .fullname }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
spec:
  {{- if hasKey $pdb "minAvailable" }}
  minAvailable: {{ $pdb.minAvailable }}
  {{- else }}
  maxUnavailable: {{ $pdb.maxUnavailable | default 1 }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "base.selectorLabels" . | nindent 6 }}
{{- end -}}

{{- define "base.hpa" -}}
{{- $a := .w.autoscaling -}}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ .fullname }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ .fullname }}
  minReplicas: {{ $a.minReplicas | default 2 }}
  maxReplicas: {{ $a.maxReplicas | default 5 }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ $a.targetCPUUtilizationPercentage | default 70 }}
{{- end -}}

{{- define "base.route" -}}
{{- $r := .w.route -}}
{{- $gw := required "gateway.name is required when a route is enabled" (.root.Values.gateway).name -}}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ .fullname }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
spec:
  parentRefs:
    - group: gateway.networking.k8s.io
      kind: Gateway
      name: {{ $gw }}
      {{- with (.root.Values.gateway).namespace }}
      namespace: {{ . }}
      {{- end }}
      {{- with (.root.Values.gateway).sectionName }}
      sectionName: {{ . }}
      {{- end }}
  hostnames:
    {{- toYaml (required "route.hostnames is required" $r.hostnames) | nindent 4 }}
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: {{ $r.pathPrefix | default "/" }}
      backendRefs:
        - name: {{ .fullname }}
          port: {{ .w.servicePort | default 80 }}
{{- end -}}

{{/* Default-deny in both directions, DNS egress always, plus the allows given in values (raw NetworkPolicy rules). */}}
{{- define "base.networkPolicy" -}}
{{- $np := .w.networkPolicy | default dict -}}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ .fullname }}{{ .suffix | default "" }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
  {{- if .hook }}
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
    argocd.argoproj.io/sync-wave: "-2"
  {{- end }}
spec:
  podSelector:
    matchLabels:
      {{- include "base.selectorLabels" . | nindent 6 }}
  policyTypes:
    - Ingress
    - Egress
  {{- if and (not .hook) $np.ingress }}
  ingress:
    {{- toYaml $np.ingress | nindent 4 }}
  {{- end }}
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
    {{- with $np.egress }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
{{- end -}}

{{- define "base.migrationJob" -}}
{{- $m := .w.migrations -}}
{{- $db := required "migrations.databaseUrlSecret (name, key) is required" $m.databaseUrlSecret -}}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ .fullname }}-migrate
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "base.labels" . | nindent 4 }}
    app.kubernetes.io/component: migrate
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
    argocd.argoproj.io/sync-wave: "-1"
spec:
  backoffLimit: {{ $m.backoffLimit | default 1 }}
  template:
    metadata:
      labels:
        {{- include "base.labels" . | nindent 8 }}
        app.kubernetes.io/component: migrate
    spec:
      restartPolicy: Never
      serviceAccountName: {{ .fullname }}-migrate
      automountServiceAccountToken: false
      priorityClassName: {{ required "priorityClassName is required" .root.Values.priorityClassName }}
      securityContext:
        {{- include "base.podSecurityContext" . | nindent 8 }}
      containers:
        - name: migrate
          image: {{ include "base.image" . | quote }}
          imagePullPolicy: {{ (.w.image).pullPolicy | default "IfNotPresent" }}
          command:
            {{- toYaml (required "migrations.command is required" $m.command) | nindent 12 }}
          {{- with $m.args }}
          args:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          env:
            - name: {{ $m.databaseUrlEnv | default "DATABASE_URL" }}
              valueFrom:
                secretKeyRef:
                  name: {{ $db.name }}
                  key: {{ $db.key }}
            {{- range $k, $v := $m.env }}
            - name: {{ $k }}
              value: {{ $v | quote }}
            {{- end }}
          resources:
            {{- toYaml ($m.resources | default .w.resources) | nindent 12 }}
          securityContext:
            {{- include "base.containerSecurityContext" . | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            {{- range .w.extraEmptyDirs }}
            - name: {{ .name }}
              mountPath: {{ .mountPath }}
            {{- end }}
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: {{ .w.tmpSizeLimit | default "64Mi" }}
        {{- range .w.extraEmptyDirs }}
        - name: {{ .name }}
          emptyDir:
            sizeLimit: {{ .sizeLimit | default "64Mi" }}
        {{- end }}
{{- end -}}
