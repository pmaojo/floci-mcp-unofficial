# 🐼 Redpanda for Floci Studio

**Redpanda** is a streaming data platform for developers. It is a Kafka-compatible message queue that is fast, reliable, and easy to use, without the need for Zookeeper.

This recipe provides a fully functional local streaming environment, complete with the Redpanda Console for visual management of your topics, brokers, and messages.

## ✨ Features
- **Kafka Compatible**: Works seamlessly with your existing Kafka client applications.
- **High Performance**: Designed to be incredibly fast and resource-efficient.
- **Redpanda Console**: A powerful UI to manage your clusters, inspect messages, and monitor health.
- **Schema Registry**: Built-in support for schema management.

## 🚀 Usage in Floci Studio
When you start the Redpanda recipe via Floci Studio, you can configure:
- **Redpanda Broker Port**: The external port to connect to the Kafka-compatible broker (default: `19092`).
- **Redpanda Console Port**: The port to access the visual management console (default: `8080`).

Connect your Kafka clients to `localhost:19092` (or your configured port).
Access the Redpanda Console at `http://localhost:8080` (or your configured port).

## 🚀 Path to AWS

**Managed service:** Amazon MSK (managed Apache Kafka)

Redpanda is Kafka-API compatible, so producers/consumers and topics behave locally exactly as on MSK.

**Deploy:** Point your Kafka bootstrap servers at the MSK cluster endpoint (add the IAM/TLS auth config).
