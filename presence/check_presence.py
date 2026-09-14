#!/usr/bin/env python3
"""Guard the field-presence surface of this repository's own protos.

WHY THIS EXISTS. Adding or removing a proto3 ``optional`` keyword is source-breaking in five
generated languages and changes what an unset field MEANS to every server that reads it, yet it is
a one-word edit that no compiler, no linter and no downstream test in this repository can see. This
walks a real ``--descriptor_set_out`` and asserts the presence surface against committed
expectations.

WHAT IT ASSERTS, and why each is a SET EQUALITY rather than a subset check:

1. The set of ``proto3_optional`` fields EQUALS ``presence/expected_optional.txt``. Set equality, so
   a keyword REMOVED fails exactly as loudly as a keyword added - a removal silently turns an unset
   field back into an indistinguishable default, which is the defect the keyword was added to fix.
2. No repeated or map field carries the keyword. ``protoc`` refuses both today, so this is a floor
   under a future protobuf release rather than a check on this one.
3. The set of singular MESSAGE fields carrying the keyword EQUALS
   ``presence/legacy_optional_message_fields.txt``. A singular message field already has presence
   WITHOUT the keyword, so the keyword buys nothing and costs a synthetic oneof that becomes public
   surface in the generated clients. Thirteen predate this guard and are left alone - removing them
   would be a second source-breaking change for zero behaviour - but a FOURTEENTH must fail, and
   because the check is a set equality it fails BY NAME.
4. A non-vacuity floor: at least ``MIN_FILES`` files and ``MIN_FIELDS`` fields must have been walked,
   and both counts are PRINTED. A guard that inspects nothing and reports success is worse than no
   guard, and the way this one would break - a glob that stops matching, a rename of the proto
   directory - is silent by construction.

It also produces ``presence/presence-manifest.json``: for every optional field, the message, name,
number, type, json_name and the measured hex of BOTH the unset encoding and the explicit-default
encoding. That file is what lets the SDK tests be descriptor-driven in languages whose generated
code carries no descriptors at all (jspb), where there is otherwise nothing to assert against.

Usage:
    python3 presence/check_presence.py            # check; non-zero exit on any violation
    python3 presence/check_presence.py --write    # regenerate the manifest, then check
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

try:
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
except ImportError:  # pragma: no cover - a missing toolchain is a BROKEN check, never a finding
    sys.stderr.write(
        "presence_check: BROKEN (not a finding): the protobuf runtime is missing.\n"
        "  This repository ships protos, not python, so nothing else here installs it. Either:\n"
        "    pip install grpcio-tools protobuf\n"
        "  or point the target at an interpreter that already has them:\n"
        "    make presence_check PRESENCE_PY=/path/to/python\n"
    )
    sys.exit(2)

REPO_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESENCE_DIR: str = os.path.join(REPO_ROOT, "presence")

# The protos this repository OWNS. ondewo/{nlu,qa,s2t,t2s,sip} are frozen copies of other APIs'
# submodules, re-assembled by `make build`; their presence surface is their own repository's
# contract and is not ours to assert on.
PROTO_FILES: Tuple[str, ...] = (
    "ondewo/vtsi/calls.proto",
    "ondewo/vtsi/projects.proto",
    "ondewo/vtsi/logs.proto",
)

EXPECTED_OPTIONAL_FILE: str = os.path.join(PRESENCE_DIR, "expected_optional.txt")
LEGACY_OPTIONAL_MESSAGE_FILE: str = os.path.join(PRESENCE_DIR, "legacy_optional_message_fields.txt")
MANIFEST_FILE: str = os.path.join(PRESENCE_DIR, "presence-manifest.json")

# Non-vacuity floor. Sized well below today's measurement (3 files, 426 fields) so honest growth or
# a deleted message does not trip it, and far above zero so a glob that stops matching does.
MIN_FILES: int = 3
MIN_FIELDS: int = 400

# FieldDescriptorProto label / type constants, spelled out rather than imported so the failure mode
# of a protobuf upgrade is a NameError here and not a silently mis-classified field.
LABEL_REPEATED: int = descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
TYPE_MESSAGE: int = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
TYPE_GROUP: int = descriptor_pb2.FieldDescriptorProto.TYPE_GROUP
TYPE_NAMES: Dict[int, str] = {
    number: name[len("TYPE_"):].lower()
    for name, number in descriptor_pb2.FieldDescriptorProto.Type.items()
}


class PresenceCheckError(Exception):
    """Raised when the descriptor set cannot be produced at all, which is never a finding."""


def build_descriptor_set(destination: str) -> None:
    """Compile PROTO_FILES into a FileDescriptorSet at ``destination``.

    Args:
        destination (str):
            Path the ``--descriptor_set_out`` is written to.

    Raises:
        PresenceCheckError:
            When no protoc is available, or when protoc exits non-zero. Both are a BROKEN CHECK, not
            a violation, and are reported as such so an empty inspection can never read as a pass.
    """
    argv: List[str] = [
        "protoc",
        "-I.",
        "--include_imports",
        f"--descriptor_set_out={destination}",
        *PROTO_FILES,
    ]
    try:
        from grpc_tools import protoc as grpc_protoc  # noqa: PLC0415  (optional dependency)
    except ImportError:
        grpc_protoc = None  # type: ignore[assignment]

    if grpc_protoc is not None:
        # grpc_tools ships its own well-known types; point the import path at them as well.
        well_known: str = os.path.join(os.path.dirname(grpc_protoc.__file__), "_proto")
        code: int = grpc_protoc.main([*argv[:1], f"-I{well_known}", *argv[1:]])
        if code != 0:
            raise PresenceCheckError(f"grpc_tools.protoc exited {code}")
        return

    from shutil import which

    binary: Optional[str] = which("protoc")
    if binary is None:
        raise PresenceCheckError(
            "no protoc available: install grpcio-tools (pip install grpcio-tools) or put protoc on PATH"
        )
    completed = subprocess.run([binary, *argv[1:]], cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise PresenceCheckError(f"protoc exited {completed.returncode}:\n{completed.stderr}")


def iter_messages(
    messages: Sequence[descriptor_pb2.DescriptorProto],
    prefix: str,
) -> Iterator[Tuple[str, descriptor_pb2.DescriptorProto]]:
    """Yield every message in ``messages``, nested types included, with its fully qualified name."""
    for message in messages:
        full_name: str = f"{prefix}.{message.name}"
        yield full_name, message
        yield from iter_messages(message.nested_type, full_name)


def read_expected(path: str) -> List[str]:
    """Read one committed expectation file.

    One fully qualified field name per line. Blank lines and whole-line ``#`` comments are ignored,
    and an inline ``#`` comment is stripped - the annotations that say WHEN a line was added are the
    only thing that makes these files readable, and a reader that treated them as part of the name
    would fail the set-equality check on a comment.

    Args:
        path (str):
            Path to the expectation file.

    Returns:
        List[str]:
            The declared field names, in file order.
    """
    names: List[str] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped: str = line.split("#", 1)[0].strip()
            if stripped:
                names.append(stripped)
    return names


def default_value_for(field: descriptor_pb2.FieldDescriptorProto) -> object:
    """Return the proto3 default for ``field``'s type, i.e. the value that means 'explicitly unset'."""
    if field.type in (descriptor_pb2.FieldDescriptorProto.TYPE_STRING,):
        return ""
    if field.type in (descriptor_pb2.FieldDescriptorProto.TYPE_BYTES,):
        return b""
    if field.type in (descriptor_pb2.FieldDescriptorProto.TYPE_BOOL,):
        return False
    if field.type in (
        descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE,
        descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT,
    ):
        return 0.0
    return 0


def build_manifest(file_set: descriptor_pb2.FileDescriptorSet) -> Dict[str, object]:
    """Build the descriptor-driven manifest of every optional field and its two measured encodings."""
    pool: descriptor_pool.DescriptorPool = descriptor_pool.DescriptorPool()
    for file_proto in file_set.file:
        pool.Add(file_proto)

    entries: List[Dict[str, object]] = []
    for file_proto in file_set.file:
        if file_proto.name not in PROTO_FILES:
            continue
        for message_name, message in iter_messages(file_proto.message_type, file_proto.package):
            for field in message.field:
                if not field.proto3_optional:
                    continue
                message_class = message_factory.GetMessageClass(pool.FindMessageTypeByName(message_name))
                unset = message_class()
                explicit = message_class()
                if field.type in (TYPE_MESSAGE, TYPE_GROUP):
                    getattr(explicit, field.name).SetInParent()
                else:
                    setattr(explicit, field.name, default_value_for(field))
                entries.append(
                    {
                        "message": message_name,
                        "field": field.name,
                        "number": field.number,
                        "type": TYPE_NAMES[field.type],
                        "type_name": field.type_name or None,
                        "json_name": field.json_name,
                        "file": file_proto.name,
                        # What the wire carries with the field untouched, and with the field
                        # EXPLICITLY set to its own default. The whole point of presence is that
                        # these two differ; a client SDK test asserts exactly this pair.
                        "unset_hex": unset.SerializeToString().hex(),
                        "explicit_default_hex": explicit.SerializeToString().hex(),
                    }
                )
    entries.sort(key=lambda entry: (str(entry["message"]), str(entry["field"])))
    return {
        "note": (
            "GENERATED by presence/check_presence.py - do not hand-edit. Regenerate with "
            "`make presence_update`. unset_hex and explicit_default_hex are the two encodings a "
            "presence-bearing field must keep distinguishable."
        ),
        "proto_files": list(PROTO_FILES),
        "optional_field_count": len(entries),
        "fields": entries,
    }


def main() -> int:
    """Run every presence check and return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="regenerate presence/presence-manifest.json instead of comparing against it",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as workdir:
        destination: str = os.path.join(workdir, "presence.desc")
        os.chdir(REPO_ROOT)
        build_descriptor_set(destination)
        with open(destination, "rb") as handle:
            file_set = descriptor_pb2.FileDescriptorSet.FromString(handle.read())

    own_files = [f for f in file_set.file if f.name in PROTO_FILES]

    optional_fields: List[str] = []
    optional_message_fields: List[str] = []
    repeated_with_keyword: List[str] = []
    field_count: int = 0

    for file_proto in own_files:
        for message_name, message in iter_messages(file_proto.message_type, file_proto.package):
            for field in message.field:
                field_count += 1
                full: str = f"{message_name}.{field.name}"
                if field.label == LABEL_REPEATED and field.proto3_optional:
                    repeated_with_keyword.append(full)
                if not field.proto3_optional:
                    continue
                optional_fields.append(full)
                if field.type in (TYPE_MESSAGE, TYPE_GROUP) and not message.options.map_entry:
                    optional_message_fields.append(full)

    # --- non-vacuity floor, printed rather than merely asserted -------------------------------
    print(f"presence_check: walked {len(own_files)} proto file(s), {field_count} field(s)")
    print(f"presence_check: {len(optional_fields)} field(s) carry the proto3 optional keyword")
    print(f"presence_check: {len(optional_message_fields)} of them are singular message fields")

    failures: List[str] = []
    if len(own_files) < MIN_FILES:
        failures.append(
            f"VACUOUS: walked {len(own_files)} file(s), floor is {MIN_FILES}. "
            "The file list resolved to too little to be a measurement."
        )
    if field_count < MIN_FIELDS:
        failures.append(
            f"VACUOUS: walked {field_count} field(s), floor is {MIN_FIELDS}. "
            "The file list resolved to too little to be a measurement."
        )

    expected_optional = set(read_expected(EXPECTED_OPTIONAL_FILE))
    actual_optional = set(optional_fields)
    for name in sorted(actual_optional - expected_optional):
        failures.append(
            f"UNDECLARED optional field: {name}. Adding the keyword is source-breaking in five "
            f"languages and changes what unset MEANS; add it to {os.path.relpath(EXPECTED_OPTIONAL_FILE, REPO_ROOT)} "
            "in the same commit, with the release note that goes with it."
        )
    for name in sorted(expected_optional - actual_optional):
        failures.append(
            f"MISSING optional field: {name} is declared in "
            f"{os.path.relpath(EXPECTED_OPTIONAL_FILE, REPO_ROOT)} but no longer carries the keyword. "
            "Removing it silently turns an unset field back into an indistinguishable default."
        )

    for name in sorted(repeated_with_keyword):
        failures.append(f"REPEATED field carries the optional keyword: {name}. Absence is already an empty list.")

    expected_legacy = set(read_expected(LEGACY_OPTIONAL_MESSAGE_FILE))
    actual_legacy = set(optional_message_fields)
    for name in sorted(actual_legacy - expected_legacy):
        failures.append(
            f"NEW singular MESSAGE field carries the optional keyword: {name}. A singular message "
            "field already has presence without it; the keyword only adds a synthetic oneof that "
            "becomes public surface in the generated clients. Drop the keyword."
        )
    for name in sorted(expected_legacy - actual_legacy):
        failures.append(
            f"STALE legacy entry: {name} is listed in "
            f"{os.path.relpath(LEGACY_OPTIONAL_MESSAGE_FILE, REPO_ROOT)} but no longer carries the keyword. "
            "Drop the line if that removal was intended - it is source-breaking."
        )

    manifest = build_manifest(file_set)
    rendered: str = json.dumps(manifest, indent=2, sort_keys=False) + "\n"
    if args.write:
        with open(MANIFEST_FILE, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        print(f"presence_check: wrote {os.path.relpath(MANIFEST_FILE, REPO_ROOT)}")
    else:
        try:
            with open(MANIFEST_FILE, encoding="utf-8") as handle:
                committed: str = handle.read()
        except FileNotFoundError:
            committed = ""
        if committed != rendered:
            failures.append(
                f"{os.path.relpath(MANIFEST_FILE, REPO_ROOT)} is out of date. Run `make presence_update` "
                "and commit it - the SDK tests in the languages without descriptors read this file."
            )

    if failures:
        print("")
        print(f"presence_check: FAILED with {len(failures)} finding(s)")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("presence_check: OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PresenceCheckError as error:
        print(f"presence_check: BROKEN (not a finding): {error}", file=sys.stderr)
        sys.exit(2)
