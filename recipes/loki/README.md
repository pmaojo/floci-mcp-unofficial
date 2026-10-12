# 📋 Loki + Grafana (Log Aggregation) for Floci Studio

**Grafana Loki** is a horizontally-scalable log aggregation system designed to be cost-effective and easy to operate. Unlike ELK, Loki indexes only metadata (labels) rather than the full log content, making it fast and lightweight. This recipe bundles Loki with a **Grafana** instance pre-configured to use Loki as a datasource.

## ✨ Features
- **Label-based Indexing**: Efficient storage and fast queries by indexing labels rather than full text.
- **LogQL**: A powerful query language similar to PromQL for filtering, aggregating and alerting on logs.
- **Grafana Integration**: Explore and visualize logs alongside your metrics in a single Grafana UI.
- **Promtail Compatible**: Ship logs from any Docker container or systemd service using Promtail.

## 🚀 Usage in Floci Studio
When you start the Loki recipe via Floci Studio, you can configure:
- **Loki Port**: Host port for the log ingestion and query API (default: `3100`).
- **Grafana Port**: Host port for the Grafana web UI (default: `3001`).
- **Grafana Admin Password**: Password for the `admin` account (default: `admin123`).

Open Grafana at `http://localhost:3001` — log in as `admin` with your configured password. Navigate to **Explore** and select the **Loki** datasource to query your logs.

Push logs to Loki directly via HTTP:
```bash
curl -X POST http://localhost:3100/loki/api/v1/push \
  -H 'Content-Type: application/json' \
  -d '{"streams":[{"stream":{"app":"myapp"},"values":[["'$(date +%s%N)'","hello from floci"]]}]}'
```

## 🚀 Path to AWS

**Managed service:** Amazon CloudWatch Logs

Loki's label-based log model mirrors CloudWatch Logs log groups and streams — your log queries and alerting rules translate directly to CloudWatch Insights.

**Deploy:** Configure your log shippers (Promtail, Fluent Bit) to forward to CloudWatch Logs and switch queries to CloudWatch Insights syntax.
