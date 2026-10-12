# ⏱️ Temporal for Floci Studio

**Temporal** is a durable workflow orchestration engine. Write long-running, fault-tolerant workflows as ordinary code — Temporal handles retries, timeouts, sagas and state persistence for you. It's a natural local complement to Step Functions and EventBridge for complex, multi-step flows. The web UI is bundled in.

## ✨ Features
- **Durable execution**: Workflows survive process crashes and restarts.
- **Built-in UI**: Inspect workflows, execution history and namespaces.
- **Polyglot SDKs**: Go, Java, TypeScript, Python and .NET.
- **SQLite backend**: Zero external dependencies for local development.

## 🚀 Usage in Floci Studio
When you start the Temporal recipe, you can configure:
- **Temporal gRPC Port**: Port for workers and clients (default: `7233`).
- **Temporal UI Port**: Port for the web UI (default: `8088`).

Point your workers and clients at `localhost:7233`, and open the UI at **http://localhost:8088** to watch workflow executions.

```bash
# Connect with the Temporal CLI
temporal --address localhost:7233 workflow list
```

> ℹ️ This recipe uses the SQLite auto-setup image, so it boots a ready-to-use cluster with no external database.

## 🚀 Path to AWS

**Managed service:** Self-host on Amazon EKS (orchestration alt: AWS Step Functions)

The same Temporal SDK workflows and activities run locally and on your cluster — identical determinism and history.

**Deploy:** Run the Temporal services on EKS with an RDS persistence store, or model the flow as an AWS Step Functions state machine.
