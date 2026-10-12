# 🐰 RabbitMQ for Floci Studio

**RabbitMQ** is a widely used, open-source message broker that supports multiple messaging protocols. It is lightweight and easy to deploy on premises and in the cloud.

This recipe includes the highly useful Management Console for easy visual inspection of queues, exchanges, and messages.

## ✨ Features
- **Message Broker**: Robust queueing and routing mechanisms (AMQP).
- **Management Console**: A web UI for managing and monitoring your RabbitMQ server.
- **Protocol Support**: Supports AMQP, MQTT, STOMP, and more.

## 🚀 Usage in Floci Studio
When you start the RabbitMQ recipe via Floci Studio, you can configure:
- **AMQP Broker Port**: The port your local application will use to connect for messaging (default: `5672`).
- **Management Console Port**: The port to access the Web Management interface (default: `15672`).
- **Admin Username**: Default admin username for the web portal (default: `guest`).
- **Admin Password**: Default admin password for the web portal (default: `guest`).

Access the Management Console at `http://localhost:15672` (or your configured port).

## 🚀 Path to AWS

**Managed service:** Amazon MQ for RabbitMQ

Amazon MQ runs upstream RabbitMQ, so exchanges, queues and AMQP behavior are identical to local.

**Deploy:** Create an Amazon MQ for RabbitMQ broker and swap the AMQP connection URI — your topology carries over.
