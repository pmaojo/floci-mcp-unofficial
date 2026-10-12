# 🐘 PostgreSQL for Floci Studio

**PostgreSQL** is a powerful, open-source object-relational database system with over 35 years of active development that has earned it a strong reputation for reliability, feature robustness, and performance.

This recipe provides a quick and easy way to spin up a local PostgreSQL database for testing and development.

## ✨ Features
- **Reliable Storage**: Rock-solid relational database engine.
- **ACID Compliant**: Full support for robust transaction processing.
- **Advanced SQL**: Supports advanced data types, JSONB, and complex queries.

## 🚀 Usage in Floci Studio
When you start the PostgreSQL recipe via Floci Studio, you can configure:
- **Database Port**: Port on your host machine to bind the PostgreSQL database (default: `5432`).
- **Username**: The superuser account username (default: `postgres`).
- **Password**: The password for the superuser database account (default: `postgres123`).
- **Initial Database**: The name of the default database created on startup (default: `postgres`).

Connect your applications using the connection string:
`postgresql://postgres:postgres123@localhost:5432/postgres` (adjusting for your configured variables).

## 🚀 Path to AWS

**Managed service:** Amazon RDS for PostgreSQL (or Aurora)

The same Postgres engine version runs locally and on RDS — identical SQL, extensions and wire protocol.

**Deploy:** Provision an RDS/Aurora PostgreSQL instance and repoint your connection string; no app changes required.
