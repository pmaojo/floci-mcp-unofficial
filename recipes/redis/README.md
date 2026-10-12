# 🔴 Redis for Floci Studio

**Redis** is an open-source, in-memory data structure store used as a highly performant distributed key-value database, cache, and message broker.

It's the perfect tool for local development requiring fast data caching, session management, or pub/sub capabilities.

## ✨ Features
- **In-Memory Store**: Blazing fast read and write operations.
- **Versatile Data Structures**: Supports strings, hashes, lists, sets, and sorted sets.
- **Caching**: Ideal for testing application cache layers locally.

## 🚀 Usage in Floci Studio
When you start the Redis recipe via Floci Studio, you can configure:
- **Redis Host Port**: Port on your host machine to bind the Redis service (default: `6379`).
- **Access Password**: Password required to connect to the Redis instance (default: `redis123`).

Connect to the Redis server using:
`redis://:redis123@localhost:6379` (adjusting for your configured variables).

## 🚀 Path to AWS

**Managed service:** Amazon ElastiCache for Redis (or MemoryDB)

The same Redis engine and RESP protocol run locally and on ElastiCache — identical commands and data structures.

**Deploy:** Provision an ElastiCache for Redis cluster and point REDIS_URL at its primary endpoint.
