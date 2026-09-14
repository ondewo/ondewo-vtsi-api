<p align="center">
    <a href="https://www.ondewo.com">
      <img alt="ONDEWO Logo" src="https://raw.githubusercontent.com/ondewo/ondewo-logos/master/github/ondewo_logo_github_2.png"/>
    </a>
</p>

# ONDEWO VTSI API

This repository contains the original interface definitions of public ONDEWO APIs that support gRPC protocols. Reading the original interface definitions can provide a better understanding of ONDEWO APIs and help you to utilize them more efficiently. You can also use these definitions with open source tools to generate client libraries, documentation, and other artifacts.

The core components of all the client libraries are built directly from files in this repo using [the proto compiler.](https://github.com/ondewo/ondewo-proto-compiler)

For an end-user, the APIs in this repo function mostly as documentation for the endpoints. For specific implementations, look in the following repos for working implementations:

* [Python](https://github.com/ondewo/ondewo-vtsi-client-python)
* [Angular](https://github.com/ondewo/ondewo-survey-client-angular)
* [JavaScript](https://github.com/ondewo/ondewo-survey-client-javascript)
* [TypeScript](https://github.com/ondewo/ondewo-survey-client-typescript)
* [NodeJS](https://github.com/ondewo/ondewo-survey-client-nodejs)

Please note that some of these implementations are works-in-progress. The repo will make clear the status of the implementation.

## Overview

ONDEWO APIs use [Protocol Buffers](https://github.com/google/protobuf) version 3 (proto3) as their Interface Definition Language (IDL) to define the API interface and the structure of the payload messages. The same interface definition is used for gRPC versions of the API in all languages.

There are several ways of accessing APIs:

1. Protocol Buffers over gRPC: You can access APIs published in this repository through [GRPC](https://github.com/grpc), which is a high-performance binary RPC protocol over HTTP/2. It offers many useful features, including request/response multiplex and full-duplex streaming.

2. ONDEWO Client Libraries:
You can use these libraries to access ONDEWO Cloud APIs. They are based on gRPC for better performance and provide idiomatic client surface for better developer experience.

The `.proto`-files of this repository are dependent on 4 other APIs:

* `Natural Language Understanding (NLU)`
* `Speech to Text (S2T)`
* `Text to Speech (T2S)`
* `Session Initiation Protocol (SIP)`

To make development easier, use the `make build` command to pull the `.proto`-files from the API repositories and copy them into the `ondewo` folder.

## Discussions

Please use the issue tracker in this repo for discussions about this API, or the issue tracker in the relevant client if it is language-specific.

## Repository Structure

```
.
├── CONTRIBUTING.md
├── Dockerfile.utils
├── docs
│   ├── index.html
│   ├── index.md
│   └── style.css
├── install_nvm.sh
├── LICENSE
├── Makefile
├── mypy.ini
├── package.json
├── requirements.txt
├── requirements-dev.txt
├── google
├── ondewo
│   ├── nlu
│   │   ├── agent.proto
│   │   ├── aiservices.proto
│   │   ├── ccai_project.proto
│   │   ├── common.proto
│   │   ├── context.proto
│   │   ├── entity_type.proto
│   │   ├── intent.proto
│   │   ├── operation_metadata.proto
│   │   ├── operations.proto
│   │   ├── project_role.proto
│   │   ├── project_statistics.proto
│   │   ├── server_statistics.proto
│   │   ├── session.proto
│   │   ├── user.proto
│   │   ├── utility.proto
│   │   └── webhook.proto
│   ├── qa
│   │   └── qa.proto
│   ├── s2t
│   │   └── speech-to-text.proto
│   ├── sip
│   │   └── sip.proto
│   ├── t2s
│   │   └── text-to-speech.proto
│   └── vtsi
│       ├── calls.proto
│       └── projects.proto
├── ondewo-nlu-api         <----- NLU API @ https://github.com/ondewo/ondewo-nlu-api
├── ondewo-s2t-api         <----- S2T API @ https://github.com/ondewo/ondewo-s2t-api
├── ondewo-sip-api         <----- SIP API @ https://github.com/ondewo/ondewo-sip-api
├── ondewo-t2s-api         <----- T2S API @ https://github.com/ondewo/ondewo-t2s-api
├── README.md
└── RELEASE.md
```

## Generate gRPC Source Code

API client libraries can be built directly from files in this repo using [the proto compiler.](https://github.com/ondewo/ondewo-proto-compiler)

## Automatic Release Process

The entire process is automated to make development easier. The actual steps are simple:

TODOs after Pull Request was merged in:

* Checkout master:
    >git checkout master
* Pull the new stuff:
    >git pull
* (If not already, run the `setup_developer_environment_locally` command):
   >make setup_developer_environment_locally
* Update the `ONDEWO_VTSI_API_VERSION` in the `Makefile`
* Add the new Release Notes in `RELEASE.md` in the format:

   ```
   ## Release ONDEWO VTSI API X.X.X       <---- Beginning of Notes

      ...<NOTES>...

   *****************                      <---- End of Notes
   ```

* `Commit and push` the changes made in `RELEASE.md` and `Makefile`
* Check the proto field-presence guard can RUN on this machine (see below):
   >make presence_check
* Release:
   >make ondewo_release

### The release now requires the proto toolchain, and fails closed without it

`make release` — and therefore `make ondewo_release` — takes `presence_check` as its **first
prerequisite**, so a release can no longer be cut against a proto tree the field-presence guard has
never read. That guard runs a real `protoc`, which it gets from **`grpcio-tools`** installed on
`${PRESENCE_PY}`, and `PRESENCE_PY` defaults to a bare `python3`.

**On a machine whose system `python3` does not have it, the release stops before doing anything.**
No release branch is created, no tag is pushed, nothing is published: the first prerequisite exits
`2` with an instruction. Exit `2` rather than `1` is the distinction the guard makes everywhere — a
check that could not run is **BROKEN**, never a clean pass and never a finding.

The supported fix is to point `PRESENCE_PY` at an interpreter that has the toolchain. **Do not drop
the prerequisite**; that is the one change that puts an unread proto tree back into a release.

```bash
python3 -m pip install grpcio-tools protobuf   # or use a venv that already has them
make presence_check PRESENCE_PY=.venv/bin/python   # verify the interpreter on its own, first
make ondewo_release PRESENCE_PY=.venv/bin/python   # then release with the same override
```

The override does reach the guard through `make ondewo_release`, even though that target runs the
release in a **sub-make** (`run_release_with_devops` calls `make release $(info)`): a variable set on
the make command line is passed down through `MAKEFLAGS`. Measured, not assumed — it is the
non-obvious half, since the target you type is not the target that runs the guard. Exporting
`PRESENCE_PY` in the environment happens to work too, because the makefile declares it with `?=`,
but prefer the command line: that form also wins against a makefile assignment, so it keeps working
if the default ever stops being conditional.

Run `make presence_check` on its own **before** `make ondewo_release`, not because the release would
skip it, but because finding out about a missing interpreter is much cheaper than finding out about
it after the version bump has been committed and pushed.

`make release` also declares `.NOTPARALLEL:`, because its steps must run in the listed order and
make guarantees left-to-right prerequisite order only for a **serial** make. Under `make -j` the
steps are free to run concurrently and in any order — measured on GNU Make 4.3, a replica of this
step list ran fully inverted under `-j4`, tagging before the guard had read a single proto.

---
The `make ondewo_release` command can be divided into 5 steps:

* running the proto field-presence guard (`presence_check`), which stops the release if it cannot run
* cloning the devops-accounts repository and extracting the credentials
* creating and pushing the release branch
* creating and pushing the release tag
* creating the GitHub release

The variable for the GitHub Access Token is inside the Makefile, but the value is overwritten during
`make ondewo_release`, because it is passed from the devops-accounts repo as an argument to the actual `release` command.

## Automatic Release Process - Clients

Every available Client of this API can be released from this repository, to make the release process for major and minor changes easier.

The generic `release_client` command depends on 4 variables:

* `ONDEWO_VTSI_API_VERSION` -- Current API version
* `GENERIC_CLIENT` -- specifies `SSH git link` to client-repository
* `RELEASEMD` -- position of `RELEASE.md` inside the client-repository
* `GENERIC_RELEASE_NOTES` -- template text of client release notes

To release all clients in sequence, use the `make release_all_clients` command.

## Proto Documentation

The documentation for this, and all other APIs and their available versions, can be found on [ondewo.github.io](https://ondewo.github.io). For Offline usage, it can also be found in the `docs` folder.

As part of the `pre-commit` hooks, `update_githubio` is run. It will preemptively stop if:

* The command is not run on the `master` branch
* There already exists a version-object with the specified version in the `data.js` of the `ondewo.github.io` repository

> :warning:  This command is dependent on your installation of NPM and NodeJS -- Make sure to install both, or run `make setup_developer_environment_locally`
