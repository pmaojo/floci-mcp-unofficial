# 🔗 n8n for Floci Studio

**n8n** is a fair-code workflow automation platform. Connect APIs, databases and services with a visual drag-and-drop editor — no glue code required. It's a great local complement to EventBridge and SNS when you want automations with a UI.

## ✨ Features
- **Visual workflows**: Build flows by wiring nodes together.
- **400+ integrations**: HTTP, databases, cloud services, messaging, and more.
- **Self-hosted**: Your data and credentials stay on your machine.
- **Persistent volume**: Workflows and credentials survive restarts.

## 🚀 Usage in Floci Studio
When you start the n8n recipe, you can configure:
- **Web Interface Port**: Host port for the n8n editor (default: `5678`).
- **Admin Username**: Basic-auth username (default: `admin`).
- **Admin Password**: Basic-auth password (default: `floci2026`).

Open **http://localhost:5678** and sign in with your configured credentials to start designing workflows.

> 💡 **Tip:** Point n8n's HTTP nodes at your Floci endpoint (`http://host.docker.internal:4566`) to automate against local AWS services.

## 🚀 Path to AWS

**Managed service:** Self-host on Amazon ECS/EKS

Workflows run identically locally and on ECS; its AWS nodes can target the Floci endpoint (4566) in dev for true parity.

**Deploy:** Run the n8n image as an ECS service with an EFS-backed /home/node/.n8n volume and an RDS Postgres backend.
