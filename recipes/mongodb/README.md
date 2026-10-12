# 🍃 MongoDB + Mongo Express for Floci Studio

**MongoDB** is a popular document-oriented NoSQL database designed for ease of development and horizontal scaling. This recipe bundles MongoDB together with **Mongo Express**, a clean web-based admin UI, so you can browse collections and documents without installing a desktop client.

## ✨ Features
- **Document Store**: Flexible JSON-like (BSON) documents with dynamic schemas.
- **Web Admin UI**: Mongo Express lets you create databases, collections and edit documents from the browser.
- **Authenticated by default**: Ships with a root user so your local data isn't wide open.

## 🚀 Usage in Floci Studio
When you start the MongoDB recipe via Floci Studio, you can configure:
- **MongoDB Port**: Host port bound to the database server (default: `27017`).
- **Mongo Express Web Port**: Host port for the admin UI (default: `8081`).
- **Root Username**: MongoDB administrator username (default: `root`).
- **Root Password**: MongoDB administrator password (default: `mongo123`).

Open the admin UI at `http://localhost:8081` (adjusting for your configured port).

Connect your applications using the connection string:
`mongodb://root:mongo123@localhost:27017/` (adjusting for your configured variables).

## 🚀 Path to AWS

**Managed service:** Amazon DocumentDB (MongoDB-compatible)

The MongoDB wire protocol you use locally is the same DocumentDB speaks — same drivers, queries and indexes.

**Deploy:** Provision a DocumentDB cluster and repoint your connection string (add the RDS CA bundle for TLS).
