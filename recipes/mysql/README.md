# 🐬 MySQL + Adminer for Floci Studio

**MySQL** is the world's most popular open-source relational database, powering millions of web applications. This recipe bundles MySQL 8 with **Adminer** — a lightweight, single-file web UI for managing databases, tables and running queries without installing a desktop client.

## ✨ Features
- **Widely Compatible**: Supported by virtually every framework, ORM and hosting provider.
- **Web Admin UI**: Adminer lets you create databases, inspect tables and run queries from the browser.
- **Authenticated by default**: Ships with a root account and a dedicated app user so your local data isn't wide open.

## 🚀 Usage in Floci Studio
When you start the MySQL recipe via Floci Studio, you can configure:
- **MySQL Port**: Host port bound to the database server (default: `3306`).
- **Adminer Web Port**: Host port for the Adminer UI (default: `8080`).
- **Root Password**: MySQL root superuser password (default: `root123`).
- **Initial Database**: Default database created on startup (default: `mydb`).
- **Username / Password**: Non-root app user credentials (default: `mysql` / `mysql123`).

Open the Adminer UI at `http://localhost:8080` — select **MySQL** as the system and log in with your configured credentials.

Connect your applications using the connection string:
`mysql://mysql:mysql123@localhost:3306/mydb` (adjusting for your configured variables).

## 🚀 Path to AWS

**Managed service:** Amazon RDS for MySQL

The same MySQL 8 engine runs locally and on RDS — identical SQL dialect, connectors and wire protocol.

**Deploy:** Provision an RDS for MySQL instance and repoint your connection string; no application changes required.
