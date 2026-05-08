---
agent_id: swift-backend
last_reviewed: 2026-05-07
notes: Wendy cloud-services project context
---

## Project Context

This codebase is the Wendy cloud-services backend (Hummingbird 2 + swift-nio + postgres-nio).

**Authentication**: mTLS via ALB header forwarding (`X-Client-Cert`). The ALB terminates the TLS, validates client certs, and forwards the cert in the header. Backend re-validates the chain — see `Sources/CloudServices/Auth/HeaderCertExtractor.swift`. Never trust the header without re-validation; ingress restriction is the only thing keeping this safe (see ADR-014).

**gRPC**: bidirectional streaming for the device telemetry RPC. Keepalive is non-default — see `Sources/CloudServices/RPC/StreamConfig.swift`. NIO HTTP/2 settings are tuned for long-lived streams.

**Database**: postgres-nio with the pool config in `Sources/CloudServices/Database/PoolConfig.swift`. Prepared statements for hot paths (auth, telemetry insert). No ORM; raw SQL with type-safe row decoders.

**Cross-cutting**: never use Foundation in the auth path — see ADR-014. Use SubProcess/Subprocess for shelling out only.
