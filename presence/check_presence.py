#!/usr/bin/env python3
"""Guard the field-presence surface of this repository's own protos.

WHY THIS EXISTS. Adding or removing a proto3 ``optional`` keyword is source-breaking in five
generated languages and changes what an unset field MEANS to every server that reads it, yet it is
a one-word edit that no compiler, no linter and no downstream test in this repository can see. This
walks a real ``--descriptor_set_out`` and asserts the presence surface against committed
expectations.

WHICH PROTOS IT WALKS. The set is DERIVED from the filesystem - every ``ondewo/vtsi/**/*.proto``,
RECURSIVELY - and never hand-maintained. A hand-written list is a guard that silently stops covering
the next file somebody adds: the new proto is walked by nothing, every printed count is unchanged,
and the check still says OK. The recursion is the same requirement one directory down, and it is not
hypothetical - a non-recursive glob shipped here and was measured: a planted
``ondewo/vtsi/v2/trunks.proto`` carrying an undeclared ``optional bool`` printed the unchanged
``walked 3 proto file(s), 426 field(s)`` and exited 0. ``ondewo/{nlu,qa,s2t,t2s,sip}`` are frozen
copies of other APIs' submodules, re-assembled by ``make build``; their presence surface is their own
repository's contract and is not ours to assert on, which is why the glob is scoped to
``ondewo/vtsi`` rather than to ``ondewo``.

WHAT IT ASSERTS, and why each is a SET EQUALITY rather than a subset check:

1. The set of ``proto3_optional`` fields EQUALS ``presence/expected_optional.txt``. Set equality, so
   a keyword REMOVED fails exactly as loudly as a keyword added - a removal silently turns an unset
   field back into an indistinguishable default, which is the defect the keyword was added to fix.
2. No repeated or map field carries the keyword. ``protoc`` refuses both today, so this is a floor
   under a future protobuf release rather than a check on this one. A map field is recognised by
   resolving the field's OWN type and reading ``options.map_entry`` on it - the message that
   DECLARES a map is an ordinary message, so reading the flag off the containing message answers
   the wrong question.
3. The set of singular MESSAGE fields carrying the keyword EQUALS
   ``presence/legacy_optional_message_fields.txt``. A singular message field already has presence
   WITHOUT the keyword, so the keyword buys nothing and costs a synthetic oneof that becomes public
   surface in the generated clients. Thirteen predate this guard and are left alone - removing them
   would be a second source-breaking change for zero behaviour - but a FOURTEENTH must fail, and
   because the check is a set equality it fails BY NAME.
4. A non-vacuity floor: at least ``MIN_FILES`` files and ``MIN_FIELDS`` fields must have been walked,
   and both counts are PRINTED together with every file name. A guard that inspects nothing and
   reports success is worse than no guard, and the way this one would break - a glob that stops
   matching, a rename of the proto directory - is silent by construction.

It also runs a hermetic SELF-TEST of the classifier before it reads a single proto. Two of the three
classes above cannot be exercised by this repository's protos at all: ``protoc`` refuses
``optional`` on a repeated or map field, so the clauses that exist as a floor under a future
protobuf release would otherwise never execute, and a defect in them would be invisible until the
day they were needed. The self-test feeds the classifier a hand-built descriptor in which that
keyword IS set on a map field, and asserts the map field is named as a map rather than mistaken for
a singular message field.

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
import glob
import json
import os
import subprocess
import sys
import tempfile
from typing import Dict, Iterator, List, NamedTuple, Optional, Sequence, Tuple

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

# The protos this repository OWNS, as a GLOB rather than a list. See the module docstring: a
# hand-maintained tuple stops covering the next file added beside it, in silence.
#
# The glob is RECURSIVE, and the `**` and the `recursive=True` below are one decision spelled in two
# places. A non-recursive `ondewo/vtsi/*.proto` covers a sibling file and nothing in a subdirectory,
# so the silent-miss this derivation exists to prevent came straight back one directory down: a
# planted `ondewo/vtsi/v2/trunks.proto` carrying an undeclared `optional bool` was walked by nothing,
# left the printed counts at `3 proto file(s), 426 field(s)` and still reported OK. Measured the
# other way round too, which is why neither half may be changed alone: `**` WITHOUT `recursive=True`
# is a literal single-segment wildcard and resolves to the nested file ALONE, dropping all three
# top-level protos - loud rather than silent, because MIN_FILES catches it, but wrong.
PROTO_GLOB: str = "ondewo/vtsi/**/*.proto"


def discover_proto_files() -> Tuple[str, ...]:
    """Return every proto this repository owns, repo-relative and sorted.

    Sorted so the walk order, the manifest and therefore the byte-for-byte manifest comparison do
    not depend on the order the filesystem happens to return. Deliberately does NOT raise on an
    empty result: an empty set is reported where it can be explained (``build_descriptor_set``) and
    is caught a second time by the ``MIN_FILES`` floor, rather than turning an import of this module
    into an exception.

    ``recursive=True`` is what gives the ``**`` in ``PROTO_GLOB`` its zero-or-more-directories
    meaning, so a proto in a SUBDIRECTORY of ``ondewo/vtsi`` is walked too; see the comment there
    for what each half does without the other.

    Returns:
        Tuple[str, ...]:
            Repo-relative POSIX paths, e.g. ``("ondewo/vtsi/calls.proto", ...)``.
    """
    found: List[str] = sorted(glob.glob(os.path.join(REPO_ROOT, *PROTO_GLOB.split("/")), recursive=True))
    return tuple(os.path.relpath(path, REPO_ROOT).replace(os.sep, "/") for path in found)


PROTO_FILES: Tuple[str, ...] = discover_proto_files()

EXPECTED_OPTIONAL_FILE: str = os.path.join(PRESENCE_DIR, "expected_optional.txt")
LEGACY_OPTIONAL_MESSAGE_FILE: str = os.path.join(PRESENCE_DIR, "legacy_optional_message_fields.txt")
MANIFEST_FILE: str = os.path.join(PRESENCE_DIR, "presence-manifest.json")

# Non-vacuity floor. MIN_FILES is today's count ON PURPOSE now that the file set is derived: the
# glob cannot resolve to FEWER files than exist, so the only three ways below the floor are the
# directory moving (which `build_descriptor_set` already refuses), a proto file being DELETED, which
# is a breaking change that must be looked at rather than absorbed by a slack floor, and
# `recursive=True` being dropped from `discover_proto_files` while `**` stays, which resolves to the
# subdirectories ALONE. The floor is a SECOND line of defence and not the first: it cannot see a
# proto the glob never matched, because an unmatched file does not lower the count - which is how a
# nested `ondewo/vtsi/v2/*.proto` went unwalked past both a floor of 3 and a printed count of 3.
# MIN_FIELDS is sized below today's 426 so honest growth or a deleted message does not trip it.
MIN_FILES: int = 3
MIN_FIELDS: int = 400

# FieldDescriptorProto label / type constants, spelled out rather than imported so the failure mode
# of a protobuf upgrade is a NameError here and not a silently mis-classified field.
LABEL_OPTIONAL: int = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
LABEL_REPEATED: int = descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
TYPE_MESSAGE: int = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
TYPE_GROUP: int = descriptor_pb2.FieldDescriptorProto.TYPE_GROUP
TYPE_STRING: int = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
TYPE_NAMES: Dict[int, str] = {
    number: name[len("TYPE_"):].lower()
    for name, number in descriptor_pb2.FieldDescriptorProto.Type.items()
}


class PresenceCheckError(Exception):
    """Raised when the descriptor set cannot be produced at all, which is never a finding."""


class Classification(NamedTuple):
    """The presence classification of one walk, kept separate from the assertions that read it."""

    field_count: int
    optional_fields: List[str]
    optional_message_fields: List[str]
    repeated_with_keyword: List[str]
    map_with_keyword: List[str]


def build_descriptor_set(destination: str) -> None:
    """Compile PROTO_FILES into a FileDescriptorSet at ``destination``.

    Args:
        destination (str):
            Path the ``--descriptor_set_out`` is written to.

    Raises:
        PresenceCheckError:
            When the proto glob matched nothing, when no protoc is available, or when protoc exits
            non-zero. All three are a BROKEN CHECK, not a violation, and are reported as such so an
            empty inspection can never read as a pass.
    """
    if not PROTO_FILES:
        raise PresenceCheckError(
            f"{PROTO_GLOB} matched no files under {REPO_ROOT}: the proto directory has been renamed "
            "or moved, so there is nothing to measure. This is a BROKEN check, not a clean run."
        )
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


def index_messages(
    file_protos: Sequence[descriptor_pb2.FileDescriptorProto],
) -> Dict[str, descriptor_pb2.DescriptorProto]:
    """Index every message in ``file_protos`` by the name a field's ``type_name`` uses.

    ``FieldDescriptorProto.type_name`` is fully qualified WITH a leading dot, so the index is keyed
    that way and a lookup needs no string surgery at the call site.

    Args:
        file_protos (Sequence[descriptor_pb2.FileDescriptorProto]):
            Every file in the descriptor set, imports included - a field may name a type declared in
            a file this repository does not own.

    Returns:
        Dict[str, descriptor_pb2.DescriptorProto]:
            ``{".package.Message.Nested": DescriptorProto}``.
    """
    index: Dict[str, descriptor_pb2.DescriptorProto] = {}
    for file_proto in file_protos:
        for full_name, message in iter_messages(file_proto.message_type, file_proto.package):
            index[f".{full_name}"] = message
    return index


def is_map_field(
    field: descriptor_pb2.FieldDescriptorProto,
    index: Dict[str, descriptor_pb2.DescriptorProto],
) -> bool:
    """Return True when ``field`` is a proto map field.

    A map field is a REPEATED field whose type is a synthetic ``*Entry`` message carrying
    ``options.map_entry``. The flag lives on that synthetic type, never on the message that declares
    the map - reading it off the declaring message answers a different question and always answers
    False, which is how the clause this replaced managed to exclude an entry's own key/value fields
    while doing nothing whatsoever about map fields.

    Args:
        field (descriptor_pb2.FieldDescriptorProto):
            The field to classify.
        index (Dict[str, descriptor_pb2.DescriptorProto]):
            The output of ``index_messages``, used to resolve ``field.type_name``.

    Returns:
        bool:
            True if the field is a map field. An unresolvable ``type_name`` returns False rather
            than raising: a map entry is always declared in the same file as its map, so a type this
            index cannot see is not one.
    """
    if field.label != LABEL_REPEATED or field.type != TYPE_MESSAGE:
        return False
    entry: Optional[descriptor_pb2.DescriptorProto] = index.get(field.type_name)
    return entry is not None and entry.options.map_entry


def classify(
    file_protos: Sequence[descriptor_pb2.FileDescriptorProto],
    index: Dict[str, descriptor_pb2.DescriptorProto],
) -> Classification:
    """Classify every field of ``file_protos`` into the buckets the assertions read.

    Kept separate from ``main`` so the self-test can drive it with a descriptor ``protoc`` refuses
    to produce, which is the only way to execute the repeated/map clauses at all.

    Args:
        file_protos (Sequence[descriptor_pb2.FileDescriptorProto]):
            The files this repository OWNS - not the whole descriptor set.
        index (Dict[str, descriptor_pb2.DescriptorProto]):
            The output of ``index_messages`` over the WHOLE descriptor set, for type resolution.

    Returns:
        Classification:
            Counts and fully qualified names, in walk order.
    """
    field_count: int = 0
    optional_fields: List[str] = []
    optional_message_fields: List[str] = []
    repeated_with_keyword: List[str] = []
    map_with_keyword: List[str] = []

    for file_proto in file_protos:
        for message_name, message in iter_messages(file_proto.message_type, file_proto.package):
            for field in message.field:
                field_count += 1
                if not field.proto3_optional:
                    continue
                full: str = f"{message_name}.{field.name}"
                optional_fields.append(full)
                if is_map_field(field, index):
                    map_with_keyword.append(full)
                elif field.label == LABEL_REPEATED:
                    repeated_with_keyword.append(full)
                elif field.type in (TYPE_MESSAGE, TYPE_GROUP):
                    # SINGULAR message field: repeated and map fields were both taken above, so this
                    # branch is the one the legacy expectation file is a set equality against.
                    optional_message_fields.append(full)

    return Classification(
        field_count=field_count,
        optional_fields=optional_fields,
        optional_message_fields=optional_message_fields,
        repeated_with_keyword=repeated_with_keyword,
        map_with_keyword=map_with_keyword,
    )


def _self_test_descriptor() -> descriptor_pb2.FileDescriptorProto:
    """Build, by hand, a file descriptor ``protoc`` would refuse to emit.

    ``protoc`` rejects ``optional`` on a repeated or on a map field, so the only way to execute the
    clauses that exist as a floor under a future protobuf release is to synthesise the descriptor
    they are waiting for. The fixture carries one of each shape the classifier must tell apart.
    """
    file_proto = descriptor_pb2.FileDescriptorProto()
    file_proto.name = "presence/self_test.proto"
    file_proto.package = "presence.selftest"
    file_proto.syntax = "proto3"

    fixture = file_proto.message_type.add()
    fixture.name = "Fixture"

    # The synthetic entry type protoc generates for `map<string, string> headers = 1;`.
    entry = fixture.nested_type.add()
    entry.name = "HeadersEntry"
    entry.options.map_entry = True
    for number, name in ((1, "key"), (2, "value")):
        entry_field = entry.field.add()
        entry_field.name = name
        entry_field.number = number
        entry_field.label = LABEL_OPTIONAL
        entry_field.type = TYPE_STRING

    headers = fixture.field.add()  # a MAP field carrying the keyword protoc refuses today
    headers.name = "headers"
    headers.number = 1
    headers.label = LABEL_REPEATED
    headers.type = TYPE_MESSAGE
    headers.type_name = ".presence.selftest.Fixture.HeadersEntry"
    headers.proto3_optional = True

    nested = fixture.field.add()  # a genuine SINGULAR message field carrying the keyword
    nested.name = "nested"
    nested.number = 2
    nested.label = LABEL_OPTIONAL
    nested.type = TYPE_MESSAGE
    nested.type_name = ".presence.selftest.Fixture"
    nested.proto3_optional = True

    tags = fixture.field.add()  # a REPEATED scalar carrying the keyword
    tags.name = "tags"
    tags.number = 3
    tags.label = LABEL_REPEATED
    tags.type = TYPE_STRING
    tags.proto3_optional = True

    plain = fixture.field.add()  # an ordinary singular scalar carrying the keyword
    plain.name = "plain"
    plain.number = 4
    plain.label = LABEL_OPTIONAL
    plain.type = TYPE_STRING
    plain.proto3_optional = True

    return file_proto


def self_test() -> List[str]:
    """Run the classifier against ``_self_test_descriptor`` and return everything it got wrong.

    Returns:
        List[str]:
            One line per mis-classification. Empty means the classifier agrees with the descriptor.
    """
    file_proto = _self_test_descriptor()
    index = index_messages([file_proto])
    result = classify([file_proto], index)

    prefix = "presence.selftest.Fixture."
    problems: List[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    expect(
        f"{prefix}headers" in result.map_with_keyword,
        "a map field carrying the optional keyword was not recognised as a map field",
    )
    expect(
        f"{prefix}headers" not in result.optional_message_fields,
        "a map field carrying the optional keyword was mistaken for a SINGULAR MESSAGE field - the "
        "map_entry flag is being read off the declaring message instead of off the field's own type",
    )
    expect(
        f"{prefix}tags" in result.repeated_with_keyword,
        "a repeated scalar carrying the optional keyword was not recognised as repeated",
    )
    expect(
        result.optional_message_fields == [f"{prefix}nested"],
        f"the singular message bucket should hold exactly {prefix}nested, holds "
        f"{result.optional_message_fields}",
    )
    expect(
        f"{prefix}plain" in result.optional_fields and f"{prefix}plain" not in result.optional_message_fields,
        "a singular scalar carrying the optional keyword was mis-bucketed",
    )
    expect(
        sorted(result.optional_fields) == sorted(f"{prefix}{n}" for n in ("headers", "nested", "plain", "tags")),
        f"every keyword-bearing field must appear in the optional set, got {result.optional_fields}",
    )
    expect(
        result.field_count == 6,
        f"the walk must reach the entry type's own key/value fields too: expected 6, got {result.field_count}",
    )
    expect(
        not [name for name in result.optional_fields if name.endswith(("HeadersEntry.key", "HeadersEntry.value"))],
        "a map entry's own key/value fields must not be reported - they carry no keyword",
    )
    return problems


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

    # The classifier is checked BEFORE the protos are: a mis-classifying guard that then reports OK
    # is the failure this whole file exists to make impossible.
    self_test_problems: List[str] = self_test()
    if self_test_problems:
        raise PresenceCheckError(
            "the classifier self-test failed, so nothing it says about the protos can be trusted:\n  - "
            + "\n  - ".join(self_test_problems)
        )
    print("presence_check: classifier self-test OK (map, repeated, singular-message and scalar cases)")

    with tempfile.TemporaryDirectory() as workdir:
        destination: str = os.path.join(workdir, "presence.desc")
        os.chdir(REPO_ROOT)
        build_descriptor_set(destination)
        with open(destination, "rb") as handle:
            file_set = descriptor_pb2.FileDescriptorSet.FromString(handle.read())

    own_files = [f for f in file_set.file if f.name in PROTO_FILES]
    result = classify(own_files, index_messages(file_set.file))

    # --- non-vacuity floor, printed rather than merely asserted -------------------------------
    print(f"presence_check: walked {len(own_files)} proto file(s), {result.field_count} field(s)")
    for name in sorted(f.name for f in own_files):
        print(f"presence_check:   {name}")
    print(f"presence_check: {len(result.optional_fields)} field(s) carry the proto3 optional keyword")
    print(f"presence_check: {len(result.optional_message_fields)} of them are singular message fields")

    failures: List[str] = []
    if len(own_files) < MIN_FILES:
        failures.append(
            f"VACUOUS: walked {len(own_files)} file(s), floor is {MIN_FILES}. "
            "The file list resolved to too little to be a measurement."
        )
    if result.field_count < MIN_FIELDS:
        failures.append(
            f"VACUOUS: walked {result.field_count} field(s), floor is {MIN_FIELDS}. "
            "The file list resolved to too little to be a measurement."
        )

    expected_optional = set(read_expected(EXPECTED_OPTIONAL_FILE))
    actual_optional = set(result.optional_fields)
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

    for name in sorted(result.repeated_with_keyword):
        failures.append(f"REPEATED field carries the optional keyword: {name}. Absence is already an empty list.")
    for name in sorted(result.map_with_keyword):
        failures.append(f"MAP field carries the optional keyword: {name}. Absence is already an empty map.")

    expected_legacy = set(read_expected(LEGACY_OPTIONAL_MESSAGE_FILE))
    actual_legacy = set(result.optional_message_fields)
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
