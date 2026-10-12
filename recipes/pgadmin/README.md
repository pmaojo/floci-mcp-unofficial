# 🐘 pgAdmin for Floci Studio

**pgAdmin** is the most popular open-source administration and development platform for PostgreSQL. Browse schemas, inspect table data, run and explain queries, manage users and roles, and monitor activity — all from a powerful web UI that runs entirely in your browser.

## ✨ Features
- **Schema Browser**: Navigate databases, schemas, tables, views, functions and sequences visually.
- **Query Tool**: Full-featured SQL editor with syntax highlighting, execution plans and result export.
- **User Management**: Create roles, manage permissions and inspect pg_hba.conf-level access controls.
- **Multi-server**: Connect to multiple PostgreSQL instances simultaneously from a single UI.

## 🚀 Usage in Floci Studio
When you start the pgAdmin recipe via Floci Studio, you can configure:
- **Web Port**: Host port for the pgAdmin web UI (default: `5050`).
- **Admin Email**: Email address used to log in (default: `admin@local.dev`).
- **Admin Password**: Password for the pgAdmin admin account (default: `pgadmin123`).

Open pgAdmin at `http://localhost:5050` and log in with your configured email and password.

To connect to the Floci `postgres` recipe, add a new server with:
- **Host**: `host.docker.internal` (or your machine's LAN IP)
- **Port**: `5432`
- **Username**: `postgres`

## 🚀 Path to AWS

**Managed service:** Amazon RDS for PostgreSQL

pgAdmin connects to any PostgreSQL-compatible server — point it at a local container or an RDS/Aurora instance using the same UI and tooling.

**Deploy:** Add your RDS endpoint as a new server in pgAdmin (using the RDS hostname and port) and manage your production database with the same tooling.
