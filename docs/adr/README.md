# Architecture Decision Records (ADR)

This directory records the significant design decisions behind `mudra-lsl`.
Format follows the Michael Nygard style (Status / Context / Decision /
Consequences).

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-lsl-binding-mne-lsl.md) | Use mne-lsl as the LSL binding | Accepted |
| [0002](0002-source-id-device-serial.md) | Use the device's hardware serial number as the LSL source_id | Accepted |
| [0003](0003-timestamps-push-chunk-autostamp.md) | Leave timestamps to push_chunk's auto-stamping | Accepted |
| [0004](0004-value-representation-uv-float32.md) | Represent values as µV / float32, and mark the scale as provisional | Accepted |
| [0005](0005-architecture-stream-publisher.md) | The StreamPublisher abstraction, and one device per process | Accepted |
| [0006](0006-license-apache-2.0.md) | License the repository under Apache-2.0 | Accepted |
| [0007](0007-packaging-uv-hatchling.md) | Package with uv + hatchling, flat layout | Accepted |
