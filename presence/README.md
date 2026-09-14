# Proto field presence guard

`make presence_check` walks a real `--descriptor_set_out` of this repository's own protos
(every `ondewo/vtsi/*.proto`) and asserts the field-presence surface against the committed
expectations in this directory. `make presence_update` regenerates the manifest after an
intended change.

## Why it exists

Adding or removing a proto3 `optional` keyword is a one-word edit that:

- is **source-breaking in five generated languages** (python, nodejs, typescript, angular, js), and
- changes what an **unset** field MEANS to every server that reads it.

Nothing else in this repository can see it. `protoc` accepts both spellings, there is no test suite
here, and the docs workflow regenerates rather than diffs. The same is true in the other direction:
a keyword silently REMOVED turns an unset field back into an indistinguishable default, which is
exactly the defect the keyword was added to fix.

## Which protos it walks

The set is **derived from the filesystem** — `ondewo/vtsi/*.proto`, sorted — and is never
hand-maintained. A literal list is a guard that stops covering the next file somebody adds, in
silence: the new proto is walked by nothing, every printed count is unchanged, and the check still
says OK. Measured before the derivation went in: dropping an `ondewo/vtsi/trunks.proto` carrying one
`optional bool` into the tree left the output byte-identical and the check green.

`ondewo/{nlu,qa,s2t,t2s,sip}` are frozen copies of other APIs' submodules, re-assembled by
`make build`. Their presence surface is their own repository's contract and is not ours to assert
on, which is why the glob is scoped to `ondewo/vtsi` rather than to `ondewo`.

## What it asserts

- **Optional fields** - SET EQUALITY against `expected_optional.txt`, so an addition and a removal
  both fail, by name.
- **Repeated and map fields** - none may carry the keyword. `protoc` refuses this today, so the
  check is a floor under a future protobuf release rather than a check on this one. A map field is
  recognised by resolving the field's **own type** and reading `options.map_entry` on it: the
  message that DECLARES a map is an ordinary message, so reading the flag off the containing
  message answers a different question and always answers `False`.
- **Singular message fields** - SET EQUALITY against `legacy_optional_message_fields.txt`. A message
  field already has presence; the keyword only adds a synthetic oneof to the public API of the
  generated clients. Thirteen predate the guard and are left alone - a FOURTEENTH fails by name.
- **Non-vacuity** - at least 3 files and 400 fields, with every file NAME printed. A guard that
  inspects nothing and reports success is worse than no guard, and that is exactly how this one
  would break. A glob that matches nothing is refused earlier still, as a BROKEN check.
- **`presence-manifest.json`** - must match what the protos produce. It is the input to the SDK
  tests, so a stale one describes a contract that is not shipped.

## The classifier self-test

Two of the three classes above **cannot be exercised by this repository's protos at all**: `protoc`
rejects `optional` on a repeated or on a map field, so those clauses exist as a floor under a future
protobuf release and would otherwise never execute — a defect in them would stay invisible until the
day they were needed, which is the worst possible moment to discover one.

So `check_presence.py` runs a hermetic self-test **before** it reads a single proto, against a
hand-built descriptor carrying the keyword on a map field, on a repeated scalar, on a singular
message field and on a singular scalar. A mis-classification is reported as **BROKEN (exit 2)**, not
as a finding: nothing the guard says about the protos can be trusted while its classifier is wrong.

## `presence-manifest.json`

GENERATED - do not hand-edit. For every optional field it records the message, field name, number,
type, `json_name`, the source file, and the **measured hex of both encodings**: `unset_hex` with the
field untouched and `explicit_default_hex` with the field explicitly set to its own default. Those
two differing is the entire observable meaning of presence.

It exists because the SDK tests cannot all be descriptor-driven on their own: the jspb-based clients
(nodejs, typescript, js) ship no descriptors at all, so there is nothing in those packages to assert
against. A committed manifest gives every language one source of truth, produced by `protoc` rather
than transcribed by hand.

Because the comparison is **byte-for-byte**, every value in it is rendered by the toolchain that
produced it, so `.github/workflows/presence.yml` PINS `grpcio-tools` and `protobuf` to the versions
the committed manifest was measured with. Unpinned, the job asserts something about whatever `pip`
resolved on the day. Measured 2026-09-15 on python 3.12.3, the manifest renders byte-identically
under grpcio-tools 1.60.0 + protobuf 4.25.3 and under 1.84.0 + protobuf 7.36.1 as well, so the pin
is not papering over a live drift - it is what turns a future renderer change into a deliberate,
reviewable bump here instead of a red build on an unrelated pull request.

## Where it runs

- `.github/workflows/presence.yml` — on `master`, on `release/**` and on every pull request.
- **`make release` takes `presence_check` as its first prerequisite.** A workflow can be skipped,
  disabled or simply not triggered by the branch a release is cut on; a make prerequisite cannot.
  Without it, `make release` cuts `release/<version>` and tags it from a proto tree the guard has
  never read — measured, with a planted undeclared `optional` field, before the prerequisite existed.

## Running it

```bash
make presence_check                                   # needs grpcio-tools on the default python3
make presence_check PRESENCE_PY=/path/to/venv/python  # or point it at an interpreter that has it
make presence_update                                  # after an INTENDED presence change
```

A missing toolchain exits `2` with an instruction, not `1`: a check that could not run is BROKEN,
never a finding. The same applies to `make release`: point `PRESENCE_PY` at an interpreter that has
the toolchain rather than dropping the prerequisite.
