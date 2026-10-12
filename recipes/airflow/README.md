# 🌬️ Apache Airflow for Floci Studio

**Apache Airflow** is the leading open-source platform for workflow orchestration — define your data pipelines as Python DAGs (Directed Acyclic Graphs), schedule them on a cron-like schedule and monitor every run in the built-in web UI.

## ✨ Features
- **Python DAGs**: Define complex dependencies, branching and retries in pure Python.
- **Rich Operator Library**: Built-in operators for HTTP, SQL, S3, Kubernetes, Spark and hundreds more.
- **Web UI**: Monitor pipeline runs, inspect task logs, trigger manual runs and backfill historical data.
- **Standalone Mode**: Single-process setup ideal for local development and testing.

## 🚀 Usage in Floci Studio
When you start the Airflow recipe via Floci Studio, you can configure:
- **Web UI Port**: Host port for the Airflow web UI (default: `8080`).
- **Admin Username**: Username for the admin account (default: `airflow`).
- **Admin Password**: Password for the admin account (default: `airflow123`).

Open the Airflow UI at `http://localhost:8080` and log in with your configured credentials.

Place your DAG files in the `airflow-dags` Docker volume to have them picked up automatically. You can mount a local folder by adjusting the compose volume binding.

## 🚀 Path to AWS

**Managed service:** Amazon MWAA (Managed Workflows for Apache Airflow)

Amazon MWAA runs the same Airflow engine — your DAG files, operators, hooks and connections work without modification.

**Deploy:** Create an MWAA environment, upload your DAG folder to the associated S3 bucket and configure the same Connections and Variables via the Airflow UI or AWS Secrets Manager.
