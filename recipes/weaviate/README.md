# 🤖 Weaviate Vector Database for Floci Studio

**Weaviate** is an open-source vector database designed for AI-native applications. Store data objects alongside their vector embeddings and perform lightning-fast semantic similarity searches — perfect for RAG pipelines, semantic search, recommendation engines and multi-modal AI applications.

## ✨ Features
- **Vector + Object Storage**: Store structured data and its embedding vectors together in a single database.
- **Multiple Vectorizer Modules**: Integrate with OpenAI, Cohere, HuggingFace or bring your own embeddings.
- **REST + gRPC APIs**: Query via a high-level REST API or the high-performance gRPC API (v4 clients).
- **GraphQL Interface**: Explore your collections and run semantic queries using Weaviate's GraphQL layer.

## 🚀 Usage in Floci Studio
When you start the Weaviate recipe via Floci Studio, you can configure:
- **HTTP Port**: Host port for the Weaviate REST API and web console (default: `8080`).
- **gRPC Port**: Host port for the gRPC API used by v4 Python/TypeScript clients (default: `50051`).

Access the Weaviate REST API at `http://localhost:8080/v1`.

Connect using the Python client:
```python
import weaviate
client = weaviate.connect_to_local(host="localhost", port=8080, grpc_port=50051)
```

## 🚀 Path to AWS

**Managed service:** Amazon OpenSearch Service (k-NN plugin)

Weaviate's REST and gRPC query APIs perform the same embedding-based similarity search that OpenSearch's k-NN index provides — the same vector search logic works on both.

**Deploy:** Create an OpenSearch domain with the k-NN plugin enabled and migrate your index schemas to OpenSearch index mappings.
