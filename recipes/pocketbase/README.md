# ⚡ PocketBase for Floci

**PocketBase** is an open-source backend consisting of an embedded database (SQLite) with real-time subscriptions, built-in user management, and a convenient Administration dashboard UI.

It is an excellent choice for rapidly prototyping MVPs, mobile apps, or any project that requires a swift backend setup without the overhead of maintaining complex databases.

## ✨ Features
- **Embedded Database**: Fast SQLite database ready to use immediately.
- **Realtime API**: Easily subscribe to database changes via Server-Sent Events (SSE).
- **Authentication**: Built-in support for user management, email/password, and OAuth2 logins.
- **Admin Dashboard**: A stunning visual interface to build collections, manage records, and configure rules.

## 🚀 Usage in Floci
PocketBase exposes both its REST API and Admin Dashboard on a single configurable port:
- **API and Admin Panel Port**: Default `8090`.

### Accessing the Dashboard
Once started, you can access the Admin Dashboard by appending `/_/` to the base URL (e.g., `http://localhost:8090/_/`).
The first time you access it, you will be prompted to create your initial admin account.

## 🚀 Path to AWS

**Managed service:** Self-host on Amazon ECS/Fargate

The single PocketBase binary runs the same locally and on Fargate — identical REST API, auth and admin UI.

**Deploy:** Run the image as a Fargate service with an EFS volume mounted at /pb_data so the SQLite store persists.
