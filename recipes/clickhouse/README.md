# 📊 ClickHouse for Floci Studio

**ClickHouse** is an open-source, column-oriented OLAP database built for real-time analytics. It crunches aggregations over billions of rows in milliseconds, speaks SQL, and ships with a friendly web **Play** console.

Great for local dashboards, log analytics, event pipelines, and anything you'd otherwise throw at Redshift or Athena.

## ✨ Features
- **Columnar & vectorized**: Extremely fast `GROUP BY` and aggregations.
- **Web Play console**: Run SQL from the browser at `/play`.
- **HTTP + native protocols**: Use `curl`, `clickhouse-client`, or any driver.
- **Persistent volume**: Tables survive restarts.

## 🚀 Usage in Floci Studio
When you start the ClickHouse recipe, you can configure:
- **HTTP / Play Port**: Host port for the HTTP interface and Play console (default: `8123`).
- **Native TCP Port**: Host port for the native protocol (default: `9000`).
- **Username** / **Password**: Credentials created on first boot (default: `default` / `clickhouse123`).
- **Default Database**: Database created on boot (default: `analytics`).

### Run a query over HTTP
```bash
echo "SELECT version()" | \
  curl "http://localhost:8123/?user=default&password=clickhouse123" --data-binary @-
```

Open the **Play** console at **http://localhost:8123/play** to write SQL interactively.

> ℹ️ The native port defaults to `9000`, which clashes with the MinIO recipe. Change it at deploy time if you run both at once.

## 🚀 Path to AWS

**Managed service:** Self-host on Amazon ECS/EKS (analytics alt: Amazon Redshift)

The exact same ClickHouse engine runs locally and in your ECS/Fargate task — identical SQL, table engines and wire protocol.

**Deploy:** Push the image to ECR and run it as an ECS service; attach an EBS/EFS volume for /var/lib/clickhouse.
