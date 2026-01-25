# Messaging

Messaging contracts and broker adapters.

Current implementation:
- Redis broker (`RedisBroker`) with consumer groups, ack/nack, and DLQ support.
- `MessageEnvelope` + `MessageHeaders` contracts for tracing and delivery metadata.