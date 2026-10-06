{{/*
Expand the name of the chart.
*/}}
{{- define "application.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "application.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "application.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Name of the component network.
*/}}
{{- define "network.name" -}}
{{- printf "%s-network" (include "application.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified component network name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "network.fullname" -}}
{{- printf "%s-network" (include "application.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Component network labels.
*/}}
{{- define "network.labels" -}}
helm.sh/chart: {{ include "application.chart" . }}
{{ include "network.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Component network selector labels.
*/}}
{{- define "network.selectorLabels" -}}
app.kubernetes.io/name: {{ include "application.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
# application: {{ .Chart.Name }}
app.kubernetes.io/component: network
isMainInterface: "yes"
tier: {{ .Values.network.tier }}
{{- end }}

{{/*
Name of the component snapshots.
*/}}
{{- define "snapshots.name" -}}
{{- printf "%s-snapshots" (include "application.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified component snapshots name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "snapshots.fullname" -}}
{{- printf "%s-snapshots" (include "application.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Component snapshots labels.
*/}}
{{- define "snapshots.labels" -}}
helm.sh/chart: {{ include "application.chart" . }}
{{ include "snapshots.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Component snapshots selector labels.
*/}}
{{- define "snapshots.selectorLabels" -}}
app.kubernetes.io/name: {{ include "application.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
# application: {{ .Chart.Name }}
app.kubernetes.io/component: snapshots
isMainInterface: "yes"
tier: {{ .Values.snapshots.tier }}
{{- end }}

{{/*
Name of the component hornet.
*/}}
{{- define "hornet.name" -}}
{{- printf "%s-hornet" (include "application.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified component hornet name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "hornet.fullname" -}}
{{- printf "%s-hornet" (include "application.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Component hornet labels.
*/}}
{{- define "hornet.labels" -}}
helm.sh/chart: {{ include "application.chart" . }}
{{ include "hornet.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Component hornet selector labels.
*/}}
{{- define "hornet.selectorLabels" -}}
app.kubernetes.io/name: {{ include "application.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
# application: {{ .Chart.Name }}
app.kubernetes.io/component: hornet
isMainInterface: "yes"
tier: {{ .Values.hornet.tier }}
{{- end }}

{{/*
Name of the component coordinator.
*/}}
{{- define "coordinator.name" -}}
{{- printf "%s-coordinator" (include "application.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified component coordinator name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "coordinator.fullname" -}}
{{- printf "%s-coordinator" (include "application.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Component coordinator labels.
*/}}
{{- define "coordinator.labels" -}}
helm.sh/chart: {{ include "application.chart" . }}
{{ include "coordinator.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Component coordinator selector labels.
*/}}
{{- define "coordinator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "application.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
# application: {{ .Chart.Name }}
app.kubernetes.io/component: coordinator
isMainInterface: "yes"
tier: {{ .Values.coordinator.tier }}
{{- end }}

{{/*
Name of the component dashboard.
*/}}
{{- define "dashboard.name" -}}
{{- printf "%s-dashboard" (include "application.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified component dashboard name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "dashboard.fullname" -}}
{{- printf "%s-dashboard" (include "application.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Component dashboard labels.
*/}}
{{- define "dashboard.labels" -}}
helm.sh/chart: {{ include "application.chart" . }}
{{ include "dashboard.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Component dashboard selector labels.
*/}}
{{- define "dashboard.selectorLabels" -}}
app.kubernetes.io/name: {{ include "application.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
# application: {{ .Chart.Name }}
app.kubernetes.io/component: dashboard
isMainInterface: "yes"
tier: {{ .Values.dashboard.tier }}
{{- end }}

{{/*
Name of the component api.
*/}}
{{- define "api.name" -}}
{{- printf "%s-api" (include "application.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified component api name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "api.fullname" -}}
{{- printf "%s-api" (include "application.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Component api labels.
*/}}
{{- define "api.labels" -}}
helm.sh/chart: {{ include "application.chart" . }}
{{ include "api.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Component api selector labels.
*/}}
{{- define "api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "application.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
# application: {{ .Chart.Name }}
app.kubernetes.io/component: api
isMainInterface: "yes"
tier: {{ .Values.api.tier }}
{{- end }}