# 📊 Metabase for Floci Studio

**Metabase** is the most popular open-source business intelligence tool — it lets anyone on your team ask questions about your data and get answers as charts, dashboards and automated reports, without writing a single line of SQL.

## ✨ Features
- **No SQL Required**: Build queries visually using the question builder, or drop into SQL when needed.
- **Rich Visualizations**: Line charts, bar charts, scatter plots, pivot tables, maps and more.
- **Multi-source**: Connect to PostgreSQL, MySQL, MongoDB, ClickHouse, Redshift, Athena and many others.
- **Scheduled Reports**: Set up automatic email and Slack deliveries for dashboards.

## 🚀 Usage in Floci Studio
When you start the Metabase recipe via Floci Studio, you can configure:
- **Web Port**: Host port for the Metabase UI (default: `3000`).

Open Metabase at `http://localhost:3000` and follow the setup wizard to connect your first database.

You can connect it directly to any other running Floci recipe — for example, point it at the `postgres` recipe using `localhost:5432`.

## 🚀 Path to AWS

**Managed service:** Amazon QuickSight

Metabase connects to the same data sources as QuickSight (RDS, Redshift, Athena) — validate your dashboards and queries locally before publishing to QuickSight.

**Deploy:** Configure QuickSight datasets pointing at your production data sources and recreate your dashboards using its visual editor.
