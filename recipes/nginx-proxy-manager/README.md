# 🔀 Nginx Proxy Manager for Floci

**Nginx Proxy Manager** allows you to expose your local web services easily and securely. It provides a beautiful, user-friendly web interface to manage Nginx proxy hosts, acting as a local API Gateway or load balancer.

## ✨ Features
- **Easy Proxying**: Map local ports to friendly domain names (e.g., `http://app.local.floci.io`).
- **Free SSL**: Built-in Let's Encrypt support to secure your local or exposed services with HTTPS.
- **Access Lists & Security**: Protect your endpoints with basic HTTP authentication or IP whitelisting.
- **Embedded Database**: Uses a lightweight SQLite database out of the box to avoid heavy external dependencies.

## 🚀 Usage in Floci
When deploying Nginx Proxy Manager via Floci, you can customize:
- **HTTP/HTTPS Ports**: The ports used to handle public web traffic (defaults to `80` and `443`).
- **Admin Panel Port**: The port used to access the management UI (default `81`).

### Default Credentials
Upon first login to the Admin Panel, use the following default credentials:
- **Email**: `admin@example.com`
- **Password**: `changeme`

You will be prompted to change these details immediately after your first login.

## 🚀 Path to AWS

**Managed service:** AWS Application Load Balancer + ACM

Terminate TLS and route hosts/paths locally exactly as an ALB + ACM certificate will in production.

**Deploy:** Recreate the proxy hosts as ALB listener rules/target groups and issue the cert in ACM.
