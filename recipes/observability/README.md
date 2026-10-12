# 📊 Observability (Prometheus & Grafana) for Floci Studio

The **Observability** stack bundles **Prometheus** and **Grafana** to provide a complete local monitoring solution for your applications and metrics.

It's the perfect way to test metrics scraping, build dashboards, and set up local alerting before deploying to production.

## ✨ Features
- **Prometheus**: A powerful systems and service monitoring system that collects metrics via a pull model.
- **Grafana**: The open observability platform for visualizing metrics with beautiful, customizable dashboards.
- **Pre-configured Integration**: Grafana comes ready to query the local Prometheus instance.

## 🚀 Usage in Floci Studio
When you start the Observability recipe via Floci Studio, you can configure:
- **Prometheus Port**: The host port to access the Prometheus UI (default: `9090`).
- **Grafana Port**: The host port to access the Grafana UI (default: `3000`).
- **Grafana Admin User**: Default `admin`.
- **Grafana Admin Password**: Default `admin`.

Access Grafana at `http://localhost:3000` (or your configured port) and Prometheus at `http://localhost:9090` (or your configured port).

## 🚀 Path to AWS

**Managed service:** Amazon Managed Grafana + Amazon Managed Service for Prometheus

The same Prometheus scrape config and Grafana dashboards you build locally run unchanged on the AWS-managed pair.

**Deploy:** Remote-write metrics to an AMP workspace and import the dashboards into Amazon Managed Grafana.
