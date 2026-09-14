# Proto field presence guard

`make presence_check` walks a real `--descriptor_set_out` of this repository's own protos
(`ondewo/vtsi/{calls,projects,logs}.proto`) and asserts the field-presence surface against the
committed expectations in this directory. `make presence_update` regenerates the manifest after an
intended change.

## Why it exists

Adding or removing a proto3 `optional` keyword is a one-word edit that:

- is **source-breaking in five generated languages** (python, nodejs, typescript, angular, js), and
- changes what an **unset** field MEANS to every server that reads it.

Nothing else in this repository can see it. `protoc` accepts both spellings, there is no test suite
here, and the docs workflow regenerates rather than diffs. The same is true in the other direction:
a keyword silently REMOVED turns an unset field back into an indistinguishable default, which is
exactly the defect the keyword was added to fix.

## What it asserts

- **Optional fields** - SET EQUALITY against `expected_optional.txt`, so an addition and a removal
  both fail, by name.
- **Repeated and map fields** - none may carry the keyword. `protoc` refuses this today, so the
  check is a floor under a future protobuf release rather than a check on this one.
- **Singular message fields** - SET EQUALITY against `legacy_optional_message_fields.txt`. A message
  field already has presence; the keyword only adds a synthetic oneof to the public API of the
  generated clients. Thirteen predate the guard and are left alone - a FOURTEENTH fails by name.
- **Non-vacuity** - at least 3 files and 400 fields, both PRINTED. A guard that inspects nothing and
  reports success is worse than no guard, and that is exactly how this one would break.
- **`presence-manifest.json`** - must match what the protos produce. It is the input to the SDK
  tests, so a stale one describes a contract that is not shipped.

## `presence-manifest.json`

GENERATED - do not hand-edit. For every optional field it records the message, field name, number,
type, `json_name`, the source file, and the **measured hex of both encodings**: `unset_hex` with the
field untouched and `explicit_default_hex` with the field explicitly set to its own default. Those
two differing is the entire observable meaning of presence.

It exists because the SDK tests cannot all be descriptor-driven on their own: the jspb-based clients
(nodejs, typescript, js) ship no descriptors at all, so there is nothing in those packages to assert
against. A committed manifest gives every language one source of truth, produced by `protoc` rather
than transcribed by hand.

## Running it

```bash
make presence_check                                   # needs grpcio-tools on the default python3
make presence_check PRESENCE_PY=/path/to/venv/python  # or point it at an interpreter that has it
make presence_update                                  # after an INTENDED presence change
```

A missing toolchain exits `2` with an instruction, not `1`: a check that could not run is BROKEN,
never a finding.
