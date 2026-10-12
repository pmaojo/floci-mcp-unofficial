# 🦙 Ollama for Floci Studio

**Ollama** runs open-source large language models locally with a single binary and an OpenAI-compatible HTTP API. Pull a model once and serve it to your apps, agents, and Lambdas — no API keys, no token bills, no data leaving your machine.

It pairs beautifully with the **Qdrant** recipe to build a fully local RAG (retrieval-augmented generation) stack.

## ✨ Features
- **OpenAI-compatible API**: Drop-in `http://localhost:11434/v1` endpoint for existing SDKs.
- **Huge model library**: Llama 3, Mistral, Phi-3, Gemma, Qwen, embeddings models, and more.
- **Persistent volume**: Pulled models survive container restarts.
- **Zero cost & private**: Everything runs on your hardware.

## 🚀 Usage in Floci Studio
When you start the Ollama recipe, you can configure:
- **API Port**: Host port for the Ollama HTTP API (default: `11434`).
- **Model Keep-Alive**: How long a model stays resident in memory after the last request (default: `5m`).

### Pull and run a model
```bash
# Pull a model into the running container
docker exec -it floci-ollama ollama pull llama3.2

# Quick chat from the CLI
docker exec -it floci-ollama ollama run llama3.2 "Explain S3 in one sentence"
```

### Call it from code
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Write a haiku about DynamoDB"
}'
```

> 💡 **Tip:** GPU acceleration is used automatically when the NVIDIA Container Toolkit is installed on the host; otherwise Ollama falls back to CPU.

## 🚀 Path to AWS

**Managed service:** Amazon Bedrock

Develop against an OpenAI-compatible chat/embeddings API locally, then call Bedrock's managed models with the same request shape.

**Deploy:** Swap the base URL/SDK for the Bedrock Runtime API (or host the model on SageMaker) — your prompt code stays the same.
