# 🔍 Elasticsearch + Kibana for Floci Studio

**Elasticsearch** is the industry-standard distributed search and analytics engine, used for full-text search, log analytics, security intelligence and more. This recipe bundles Elasticsearch 8 with **Kibana** — the visualization and exploration UI for building dashboards, running Lens queries and navigating your indices.

## ✨ Features
- **Powerful Search**: Full-text search, fuzzy matching, aggregations and vector search in a single engine.
- **Kibana UI**: Build dashboards, explore indices and run ad-hoc queries from the browser.
- **Security enabled**: Ships with TLS and a built-in `elastic` superuser — no open access by default.

## 🚀 Usage in Floci Studio
When you start the Elasticsearch recipe via Floci Studio, you can configure:
- **Elasticsearch Port**: Host port for the HTTP API (default: `9200`).
- **Kibana Port**: Host port for the Kibana UI (default: `5601`).
- **Elastic Password**: Password for the `elastic` superuser (default: `elastic123`).

Open Kibana at `http://localhost:5601` and log in as `elastic` with your configured password.

Query the REST API directly:
```
curl -u elastic:elastic123 http://localhost:9200
```

## 🚀 Path to AWS

**Managed service:** Amazon OpenSearch Service

Amazon OpenSearch Service is a managed fork of Elasticsearch — the same query DSL, index mappings and REST API work on both.

**Deploy:** Create an Amazon OpenSearch domain and update your endpoint to point at its HTTPS address; index and search calls are wire-compatible.
