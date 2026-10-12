# ⚡ Supabase for Floci Studio

**Supabase** is an open-source Firebase alternative built on PostgreSQL. This recipe spins up the core Supabase stack — a managed PostgreSQL database, an auto-generated REST API via PostgREST and the full Supabase Studio dashboard for browsing tables, running queries and managing your schema.

## ✨ Features
- **PostgreSQL First**: Full Postgres with row-level security, extensions and a rich SQL dialect.
- **Auto REST API**: PostgREST automatically exposes every table and view as a RESTful endpoint.
- **Studio Dashboard**: Browse schema, inspect data, run SQL and manage API keys from a polished web UI.
- **JWT Auth-ready**: Configured with anon and service-role JWT keys out of the box.

## 🚀 Usage in Floci Studio
When you start the Supabase recipe via Floci Studio, you can configure:
- **Studio Port**: Host port for the Supabase Studio UI (default: `3000`).
- **PostgreSQL Port**: Host port for direct DB connections (default: `5432`).
- **Database Password**: PostgreSQL superuser password (default: `supabase123`).
- **JWT Secret**: Secret used to sign tokens (default: Supabase dev secret — change for production).
- **Anon Key / Service Key**: Pre-generated JWT tokens for client and server-side SDK calls.

Open Studio at `http://localhost:3000`.

Connect your Supabase client SDK:
```js
const supabase = createClient('http://localhost:3000', '<ANON_KEY>')
```

Connect directly to Postgres:
`postgresql://postgres:supabase123@localhost:5432/postgres`

## 🚀 Path to AWS

**Managed service:** AWS Amplify + Amazon RDS + Amazon Cognito

Supabase wraps standard PostgreSQL — your schema, queries and RLS policies run on RDS without changes; Auth maps to Cognito and Storage maps to S3.

**Deploy:** Migrate your PostgreSQL schema to RDS, replace Supabase Auth with Cognito user pools, swap Supabase Storage for S3 presigned URLs, and update client SDKs to point at the new endpoints.
