{{/*
Expand the name of the chart.
*/}}
{{- define "drift.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "drift.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label.
*/}}
{{- define "drift.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "drift.labels" -}}
helm.sh/chart: {{ include "drift.chart" . }}
{{ include "drift.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "drift.selectorLabels" -}}
app.kubernetes.io/name: {{ include "drift.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
ServiceAccount name.
*/}}
{{- define "drift.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "drift.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Secret name: use existingSecret if set, otherwise chart-managed secret.
*/}}
{{- define "drift.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "drift.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Database URL.
*/}}
{{- define "drift.databaseUrl" -}}
{{- printf "postgresql+asyncpg://drift:$(POSTGRES_PASSWORD)@%s-postgresql:5432/drift" (include "drift.fullname" .) }}
{{- end }}

{{/*
Redis URL.
*/}}
{{- define "drift.redisUrl" -}}
{{- printf "redis://:$(REDIS_PASSWORD)@%s-redis-master:6379/0" (include "drift.fullname" .) }}
{{- end }}

{{/*
MinIO endpoint.
*/}}
{{- define "drift.minioEndpoint" -}}
{{- printf "%s-minio:9000" (include "drift.fullname" .) }}
{{- end }}
