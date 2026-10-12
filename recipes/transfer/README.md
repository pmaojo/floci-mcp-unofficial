# 📁 AWS Transfer Family (SFTP) for Floci Studio

**AWS Transfer Family (SFTP)** recipe provides a high-performance local SFTP server that emulates the AWS Transfer Family service.

It allows you to connect and transfer files using standard SFTP clients or test file transfer integration within your applications locally.

## ✨ Features
- **Local SFTP Server**: Emulates AWS Transfer Family secure file transfer over SSH.
- **Easy Integration**: Test file uploads, downloads, and processing workflows locally.
- **Standard Clients**: Connect using any standard SFTP client (e.g., FileZilla, Cyberduck, or CLI tools).

## 🚀 Usage in Floci Studio
When you start the AWS Transfer Family recipe via Floci Studio, you can configure:
- **SFTP Host Port**: Port on your host machine to bind the SFTP service (default: `2222`).
- **Username**: SFTP user name for authentication (default: `floci`).
- **Password**: SFTP user password for authentication (default: `flocipass`).

Connect using an SFTP client:
`sftp -P 2222 floci@localhost` (adjusting for your configured variables).

## 🚀 Path to AWS

**Managed service:** AWS Transfer Family (SFTP)

Move files over SFTP locally exactly as clients will against a Transfer Family server — same protocol and auth.

**Deploy:** Provision an AWS Transfer Family SFTP server backed by an S3 bucket and migrate the users.
