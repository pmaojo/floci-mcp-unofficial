# ✉️ Mailpit for Floci

**Mailpit** is a small, fast, and highly capable email testing tool that acts as an SMTP server and provides a modern web interface to view your outgoing emails.

It is the perfect companion for local development when you need to test email delivery (like password resets, notifications, etc.) without actually sending them to real users or setting up a complex cloud SES provider.

## ✨ Features
- **Local SMTP Server**: Captures all emails sent by your application.
- **Modern Web UI**: Beautiful and fast interface to inspect emails, including HTML, text, and raw headers.
- **Link & Spam Analysis**: Built-in tools to check links and test your emails against spam filters.
- **Lightweight**: Consumes minimal resources.

## 🚀 Usage in Floci
When you start Mailpit via Floci, you can configure:
- **SMTP Port**: The port your local application will use to send emails to Mailpit (default: `1025`).
- **Web Interface Port**: The port to access the Mailpit web dashboard (default: `8025`).

Simply configure your app's SMTP settings to `localhost` and the configured SMTP port, and you're good to go!

## 🚀 Path to AWS

**Managed service:** Amazon SES

Send over plain SMTP locally (captured by Mailpit) exactly as you will to the SES SMTP endpoint — same MIME, headers and auth.

**Deploy:** Verify a domain/identity in SES and point your SMTP host/port/credentials at the SES SMTP relay.
