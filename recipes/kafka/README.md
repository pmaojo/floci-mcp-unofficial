# 📨 Apache Kafka + Kafka UI for Floci Studio

**Apache Kafka** is the industry-standard distributed event streaming platform, used for building real-time data pipelines, event-driven microservices and stream processing applications. This recipe runs Kafka 3.7 in KRaft mode (no ZooKeeper required) and bundles **Kafka UI** — a polished web console for managing topics, consumer groups, offsets and messages.

## ✨ Features
- **KRaft Mode**: No ZooKeeper dependency — simpler setup, faster startup and lower memory footprint.
- **Kafka UI**: Browse topics, produce test messages, inspect consumer lag and monitor brokers from the browser.
- **Auto topic creation**: New topics are created automatically when producers publish to them.

## 🚀 Usage in Floci Studio
When you start the Kafka recipe via Floci Studio, you can configure:
- **Kafka Broker Port**: Host port for producer/consumer connections (default: `9092`).
- **Kafka UI Port**: Host port for the web console (default: `8082`).

Open Kafka UI at `http://localhost:8082`.

Connect your producers and consumers with bootstrap server `localhost:9092`.

```python
from kafka import KafkaProducer
producer = KafkaProducer(bootstrap_servers='localhost:9092')
producer.send('my-topic', b'hello world')
```

## 🚀 Path to AWS

**Managed service:** Amazon MSK (Managed Streaming for Apache Kafka)

Amazon MSK runs standard Apache Kafka — the same producer/consumer APIs, topic configuration and wire protocol work without modification.

**Deploy:** Create an MSK cluster and swap the bootstrap server address in your producers and consumers; no code changes required.
