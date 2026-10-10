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
* [Angular](https://github.com/ondewo/ondewo-vtsi-client-angular)
* [JavaScript](https://github.com/ondewo/ondewo-vtsi-client-js)
* [TypeScript](https://github.com/ondewo/ondewo-vtsi-client-typescript)
* [NodeJS](https://github.com/ondewo/ondewo-vtsi-client-nodejs)

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

## VTSI Services

The VTSI surface is six gRPC services in `ondewo/vtsi/` (package `ondewo.vtsi`). The rendered reference of every
message, field and enum value is [docs/index.md](docs/index.md) (also `docs/index.html`).

| Service | File | What it manages |
| --- | --- | --- |
| `Projects` | `projects.proto` | VTSI projects: create, update, deploy and undeploy the per-project Asterisk |
| `Calls` | `calls.proto` | Callers (outbound), listeners (inbound), scheduled callers, calls, and the status streams |
| `Campaigns` | `campaigns.proto` | Campaigns: batches of outbound calls with a parallel-call limit and retries |
| `Events` | `events.proto` | `VtsiEvent` notifications: event subscriptions, webhooks and the event stream |
| `Logs` | `logs.proto` | Captured logs of the per-call containers |
| `Softphones` | `softphones.proto` | SIP accounts for humans using a softphone |

Errors of the `Campaigns` and `Events` services, and of `Calls.AddCallersToCampaign` /
`Calls.AddScheduledCallersToCampaign`, are reported as gRPC status codes, never in an `error_message` field.

`CommonServicesConfig`, `SipCallerConfig` and the messages they are built from are declared in `call_configs.proto`
(no service), shared by `calls.proto` and `campaigns.proto`.

Every `List*` request, and `CreateCampaign`, `GetCampaign`, `UpdateCampaign` and `DeleteCampaign`, accepts an
optional `field_mask` for a partial response: field paths relative to the returned resource (for a listing, to its
element type); the identifying field (`name`; `log_stream` and `seq` for a `CallLogEntry`) is always populated; unset
or empty returns every field; an unknown path is `INVALID_ARGUMENT`. The mask is applied after any view and any
redaction.

### Campaigns

A **campaign** is a named set of outbound calls that VTSI places while keeping at most `max_parallel_calls` of them
running at the same time. 100 callers added to a campaign with `max_parallel_calls = 10` are never more than 10
calls being set up or connected at once; the next call starts when one ends.

* **Creating and filling a campaign.** `CreateCampaign` creates an empty campaign in state `CREATED`. Calls are added
  with `Calls.AddCallersToCampaign` or `Calls.AddScheduledCallersToCampaign`, whose required `campaign_assignment`
  names either an existing campaign (`campaign_name`, or `display_name`, resolved in the request's
  `vtsi_project_name`) or a new one (`new_campaign`). The request is atomic (the campaign, every campaign call and every scheduled caller are
  stored, or nothing is), its callers are NOT started by the request itself, and `start_mode` (`CampaignStartMode`) decides whether the
  campaign starts dialling. A scheduled call of a campaign starts at or after its scheduled time AND when the
  campaign has a free slot.
* **Names.** A campaign's resource name is `projects/<project_uuid>/campaigns/<campaign_uuid>`; an empty
  `display_name` becomes `campaign-<campaign_uuid>`. Display names are unique per project, so every RPC about one
  campaign accepts either the resource name or the `display_name` together with the request's
  `vtsi_project_name` (required with a display name). The `CampaignDisplayName` message of 9.0.0 was removed in
  9.1.0; its field numbers are `reserved`.
* **Call defaults.** `campaign_common_services_config` (a `CommonServicesConfig`) and `campaign_sip_caller_config`
  (a `SipCallerConfig`) are the defaults of every call of the campaign. They are read live whenever a campaign call
  is dispatched, retries included: the call's own `StartCallerRequest` config is merged over a copy of them
  (protobuf `MergeFrom`, the call winning). Set them on `CreateCampaign` or `new_campaign`, change them with
  `UpdateCampaign` (whole or by nested sub-path); unset, they change nothing. Both messages live in
  `call_configs.proto`, which `calls.proto` re-exports with `import public`.
* **Lifecycle.** `StartCampaign` starts a `CREATED` campaign. `StopCampaign` is graceful: no new call is started, the
  calls that are running continue to their natural end, then the campaign is `STOPPED`. `HardStopCampaign` hangs up
  every running call of the campaign immediately; the campaign stays `HARD_STOPPING` until the end of each call is
  confirmed, then it is `HARD_STOPPED`, and the calls it ended are `CANCELLED`. `ResumeCampaign` continues a
  `STOPPING`, `STOPPED` or `HARD_STOPPED` campaign with the calls that have not finished. A campaign whose calls are
  all finished is `COMPLETED`; adding calls makes it `RUNNING` again.
* **Retries.** `max_attempts` (default 1 = no retry, at most 10) and `retry_delay` (default 60 s) apply to every call
  of the campaign. A call counts as failed only after its last attempt; a failure that cannot succeed by repetition
  (a rejected credential, an invalid configuration) is not retried. Both settings, `display_name` and
  `max_parallel_calls` can be changed with `UpdateCampaign` in every state; lowering `max_parallel_calls` never ends
  a running call.
* **Progress.** `GetCampaignStatistics` counts every call in exactly one of `not_started`, `in_progress`,
  `retry_pending`, `completed`, `failed` and `cancelled`, plus `total_attempts` and `calls_retried`. The four buckets
  "completed / failed / in progress / not started" are `completed`, `failed + cancelled`,
  `in_progress + retry_pending` and `not_started`. `ListCampaignCalls` returns each call with its SIP status type,
  SIP status description, attempts and, on request, its attempt history. `StreamCampaignStatus` streams a snapshot of
  the project's campaigns and then every change.
* **Rolling updates fail closed.** A server replica that predates `AddCallersToCampaign` /
  `AddScheduledCallersToCampaign` answers them with `UNIMPLEMENTED` and starts nothing. Do not fall back to
  `StartCallers` on `UNIMPLEMENTED`; retry later. `StartCallers` / `StartScheduledCallers` no longer carry a
  campaign field: development builds of 9.0.0 used field 3 for it, the number is `reserved`, and a server refuses
  a request that still carries it with `INVALID_ARGUMENT` instead of starting every caller.

### Idempotent retries of batch requests

`StartCallers`, `StartListeners`, `StartScheduledCallers`, `AddCallersToCampaign` and
`AddScheduledCallersToCampaign` accept an optional `idempotency_key` (at most 255 printable ASCII characters, no
whitespace). Send a fresh key, e.g. a UUID, with every new batch and the SAME key with every retry of it: a retry
after a timeout or `UNAVAILABLE` then returns the first attempt's response instead of starting a second batch, on
whichever server replica it lands. The same key with a different request is refused with `INVALID_ARGUMENT`; a retry
while the first attempt is still running is answered `ABORTED` and should be retried after a pause. A failed first
attempt stores nothing. A replayed response carries no `common_services_config`. The server keeps a key for 24 hours
by default.

### Status streams

`Calls.StreamCallerStatus`, `Calls.StreamListenerStatus` and `Calls.StreamScheduledCallerStatus` send a snapshot
(`snapshot = true`) of the matching callers, listeners or scheduled callers, then every resource whose call or SIP
status changed (`CallResourceStatus`: call, active flag, SIP status type and description, times, phone number,
scheduled-caller state, campaign), plus keep-alive messages. `Campaigns.StreamCampaignStatus` does the same for
campaigns and, with `include_calls`, their campaign calls. A server without a free stream slot answers
`RESOURCE_EXHAUSTED`; a stream ends at the server's maximum stream duration with `end_reason` set.

### VtsiEvents, event subscriptions and webhooks

Every key event and status change of VTSI is one value of the enum `VtsiEvent`, grouped by resource in blocks of 100:
calls (1xx), callers (2xx), listeners (3xx), scheduled callers (4xx), campaigns (5xx), VTSI projects (6xx), the
project's Asterisk (7xx), softphone accounts (8xx) and the event system itself (9xx). Each event is delivered as a
`VtsiEventMessage` with a unique `event_id`, the resource it is about, its time, the SIP status where there is one,
the campaign where known and a per-resource `resource_sequence`.

* **Event subscriptions** (per project) choose which events are delivered (`events`, or `all_events`), optionally
  narrowed by `resource_name_prefixes` and `campaign_names`, and to which webhooks.
* **Webhooks** (per project) are an `http://` or `https://` URL, `POST` (default) or `PUT`, a timeout and optional
  **custom headers**, e.g. `Authorization`. Each event is sent as one HTTP request whose JSON body is the
  `VtsiEventMessage`. Custom header VALUES are write-only: every RPC returns them as `********`, an update that sends
  `********` keeps the stored value, and the server never logs them. Moving a webhook's `url` to another origin
  (scheme, host or port) while headers are stored requires re-sending `custom_headers` with their real values (or
  an empty map) in the same update; the stored values never follow the url to a new origin. `TestWebhook` sends one test event at once and
  reports the outcome.
* **`SubscribeVtsiEvents`** streams a project's events, selected by a stored subscription or an inline
  `VtsiEventFilter`; after a disconnect, the last `resume_token` continues where the stream stopped, within the
  server's event retention.
* **Webhook delivery is best effort.** Each event is sent to a webhook as at most a few HTTP requests with backoff,
  kept in the memory of the server replica that produced it; an overloaded server or a failing webhook drops events
  rather than slowing calls down. The same event can arrive more than once and events can arrive out of order:
  de-duplicate by `event_id`, order by `resource_sequence` per `resource_name`, and reconcile with the status RPCs.

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
│       ├── campaigns.proto
│       ├── events.proto
│       ├── logs.proto
│       ├── projects.proto
│       └── softphones.proto
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

### The release requires the proto toolchain, and fails closed without it

`make release` — and therefore `make ondewo_release` — takes `presence_check` as its **first
prerequisite**, so a release can no longer be cut against a proto tree the field-presence guard has
never read. That guard runs a real `protoc`, which it gets from **`grpcio-tools`**.

**With [uv](https://docs.astral.sh/uv/) installed, `make presence_check` works out of the box.** With
`PRESENCE_PY` unset the targets run the guard through `PRESENCE_RUNNER`, i.e. `uv run --no-project`
with the same `grpcio-tools` / `protobuf` pins as `.github/workflows/presence.yml` (the manifest is
compared byte-for-byte, so the versions are pinned and change in both places together). uv builds that
environment in its own cache; nothing is installed into the checkout or the system python.

**Without uv, the release stops before doing anything.** The runner is then a bare `python3`, which
usually has no `grpcio-tools`: no release branch is created, no tag is pushed, nothing is published,
and the first prerequisite exits `2` with an instruction. Exit `2` rather than `1` is the distinction
the guard makes everywhere — a check that could not run is **BROKEN**, never a clean pass and never a
finding. **Offline**, uv resolves the pins on its first run and fails with its own resolver error (uv's
exit code, not `2`): still closed, but warm uv's cache once while online, or use the override below.

`PRESENCE_PY` always wins over the runner: point it at an interpreter that has the toolchain. **Do not
drop the prerequisite**; that is the one change that puts an unread proto tree back into a release.

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
skip it, but because finding out about a missing toolchain is much cheaper than finding out about
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
