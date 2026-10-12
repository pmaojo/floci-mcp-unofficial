# 🐻 Uptime Kuma for Floci Studio

**Uptime Kuma** is a self-hosted monitoring and status page tool with a beautiful, reactive UI. Monitor your websites, APIs, TCP ports and DNS records, and get instant notifications through Slack, Telegram, email and 90+ other integrations.

## ✨ Features
- **Multi-protocol Monitoring**: HTTP(S), TCP, DNS, Ping, Docker container status and more.
- **Status Pages**: Create public or private status pages for your services with custom domains.
- **90+ Notifications**: Slack, Telegram, Discord, PagerDuty, email and many more integrations.
- **No Configuration Files**: Entire setup managed through the reactive web UI — no YAML required.

## 🚀 Usage in Floci Studio
When you start the Uptime Kuma recipe via Floci Studio, you can configure:
- **Web Port**: Host port for the Uptime Kuma dashboard (default: `3001`).

Open Uptime Kuma at `http://localhost:3001` — you'll be prompted to create an admin account on first launch.

Add monitors for any of your other Floci recipes by pointing at their respective `localhost` ports (e.g., `http://localhost:5432` for PostgreSQL TCP check).

## 🚀 Path to AWS

**Managed service:** Amazon Route 53 Health Checks

Uptime Kuma monitors the same endpoints that Route 53 Health Checks poll — validate your alerting thresholds and notification flows locally before wiring up CloudWatch alarms.

**Deploy:** Create Route 53 Health Checks for your production endpoints and configure CloudWatch alarms to trigger SNS notifications on failure.
