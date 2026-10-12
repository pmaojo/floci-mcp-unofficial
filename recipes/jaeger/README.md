# 🔭 Jaeger for Floci Studio

**Jaeger** is an open-source, end-to-end distributed tracing system. It helps you monitor and troubleshoot transactions in complex microservice architectures by visualizing request flows, latencies and service dependencies.

This recipe runs the Jaeger **all-in-one** image with the OpenTelemetry (OTLP) collector enabled, so any OpenTelemetry-instrumented application can push traces directly.

## ✨ Features
- **OTLP Ready**: Accepts traces over OTLP gRPC (`4317`) and OTLP HTTP (`4318`) out of the box.
- **Trace Explorer**: Search, filter and inspect spans through the built-in web UI.
- **Dependency Graph**: Visualize how your services call each other.

## 🚀 Usage in Floci Studio
When you start the Jaeger recipe via Floci Studio, you can configure:
- **Jaeger UI Port**: Host port for the web UI (default: `16686`).
- **OTLP gRPC Port**: Host port for OTLP gRPC trace ingestion (default: `4317`).
- **OTLP HTTP Port**: Host port for OTLP HTTP trace ingestion (default: `4318`).

Open the UI at `http://localhost:16686` (adjusting for your configured port).

Point your OpenTelemetry exporter at `http://localhost:4318` (HTTP) or `localhost:4317` (gRPC) to start sending traces.

## 🚀 Path to AWS

**Managed service:** AWS X-Ray (via OpenTelemetry / ADOT)

Emit OTLP spans locally to Jaeger exactly as you will to X-Ray — same instrumentation, no app changes.

**Deploy:** Swap the OTLP exporter target for the AWS Distro for OpenTelemetry (ADOT) collector that ships traces to X-Ray.
