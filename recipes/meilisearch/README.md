# 🔍 Meilisearch for Floci Studio

**Meilisearch** is an incredibly fast, open-source search engine designed for providing a stellar search experience with an intuitive REST API.

It's perfect for integrating highly relevant, typo-tolerant search functionality into your applications without complex configurations.

## ✨ Features
- **Lightning Fast**: Returns search results in under 50 milliseconds.
- **Typo Tolerance**: Handles typos naturally right out of the box.
- **RESTful API**: Easy to integrate with any stack.
- **Customizable**: Allows fine-tuning of search ranking rules and synonyms.

## 🚀 Usage in Floci Studio
When you start the Meilisearch recipe via Floci Studio, you can configure:
- **Meilisearch Port**: The host port to access the API (default: `7700`).
- **Master Key**: The secret key to secure your Meilisearch instance (default: `masterKey`).

Access the Meilisearch API at `http://localhost:7700` (or your configured port).

## 🚀 Path to AWS

**Managed service:** Amazon OpenSearch Service (or self-host on ECS)

Index and full-text search locally with the same documents and ranking you will run in production.

**Deploy:** Either self-host Meilisearch on ECS behind an ALB, or migrate the index to an Amazon OpenSearch domain.
