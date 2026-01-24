# Messaging (Stub)

Messaging contracts and broker adapters.

Current implementation:
- Redis Streams broker (`RedisStreamsBroker`) with consumer groups, ack/nack, and DLQ support.
- `MessageEnvelope` + `MessageHeaders` contracts for tracing and delivery metadata.
- Legacy list-backed queue via `RedisQueue` (deprecated).
