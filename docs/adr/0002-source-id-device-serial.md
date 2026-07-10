# ADR-0002: Use the device's hardware serial number as the LSL source_id

- Status: Accepted (2026-07-10)

## Context

LSL consumers use `source_id` as the key for "is this the same physical device
as last time." Two candidates:

- The BLE address/handle `bleak` returns.
- The device's own serial number (read from the standard GATT characteristics
  `0x2a25` = SERIAL_RIGHT and `0x2a27` = SERIAL_LEFT, combined as
  `serial = left * 1_000_000 + right`).

The BLE address is unstable across platforms. On macOS, `bleak` surfaces a
CoreBluetooth-assigned UUID rather than the real hardware MAC (the same class
of problem hit in `mudra-viewer`'s reconnection issue). On Linux/Windows it is
a real MAC, but can still change under privacy-mode randomization or adapter
swaps.

## Decision

Read the serial number once at connect time and use `str(serial)` as
`source_id`. If it can't be read or parsed, fall back to the BLE address and
log a warning (the outlet stays usable either way).

Serial parsing treats the value as a hex string (per the signal spec), ASCII
decoded and parsed with `int(x, 16)` (`constants.parse_serial_field`). The
combination formula lives in `constants.combine_serial`.

## Consequences

- Recordings of the same physical band can be tied together across sessions
  and platforms.
- Reading the serial costs two extra BLE reads at connect time (acceptable).
- The fallback path logs a warning, so the provenance of `source_id` is always
  traceable from the logs.
