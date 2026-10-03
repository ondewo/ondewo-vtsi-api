# Release History

*****************

## Release ONDEWO VTSI API 9.0.0

### Breaking changes

* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) Renamed
  `AsteriskConfigsFiles.sip_conf_file_string` to `pjsip_conf_file_string`. The `chan_sip` channel driver the
  old name referred to was removed in Asterisk 21; the configuration file an Asterisk 22 server reads is
  `pjsip.conf`, so the field carried a name that described a file no supported Asterisk parses. **Field
  number 1 and type `string` do not change and no `json_name` override is added**, so the change is binary
  wire-compatible in both directions and source-breaking only. The three sibling fields keep their names:
  `extensions.conf`, `queues.conf` and `modules.conf` exist unchanged under `res_pjsip` and only their
  CONTENT changes. The accessor that moves, per language, measured against the generated 8.7.x client trees:

  | Client | 8.7.x | 9.0.0 |
  | --- | --- | --- |
  | python | `sip_conf_file_string` attribute, constructor keyword and `ClearField` literal | `pjsip_conf_file_string` |
  | angular | `sipConfFileString` property (23 references) | `pjsipConfFileString` |
  | nodejs, typescript, js | `getSipConfFileString()` / `setSipConfFileString()`, `sipConfFileString` on `AsObject` | `getPjsipConfFileString()` / `setPjsipConfFileString()` |

  The field deliberately does NOT gain the `optional` keyword. On the create path `""` and unset are the
  same instruction — build the Asterisk configuration from the blueprint — so presence would add a third
  state that no server reads.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) Eleven singular scalars in
  `ondewo/vtsi/calls.proto` gained the `optional` keyword, so that "the caller said nothing" stops being
  indistinguishable from "the caller said the default":
  `InterruptionHandlingConfig.transcribe_on_disabled_interruptions`,
  `TurnDetectionConfig.turn_detection_system_prompt`, `TurnDetectionConfig.turn_detection_user_prompt`,
  `AudioObjectStorageConfig.activate_audio_object_storage`,
  `AudioObjectStorageServicesActivationConfig.activate_s2t` and `.activate_t2s`,
  `MessageBrokerConfig.activate_message_broker`, and
  `MessageBrokerServicesActivationConfig.activate_s2t`, `.activate_nlu`, `.activate_t2s` and
  `.activate_sip`. Each keeps its field number and wire type; `optional` only adds explicit presence,
  compiling to a synthetic one-member oneof that exists in the descriptor and not on the wire. The listed
  fields are singular scalars only — a repeated or map field cannot take the keyword, a oneof member cannot
  take it, and a singular message field already has presence without it.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) The comment on
  `ScheduledCaller.call_name` lost the words "asterisk sip", matching its `Caller` and `Listener` siblings.
  Listed here only because it is a source-visible change: it moves no descriptor byte, measured — the
  descriptor set and the generated `calls_pb2.py` are byte-identical before and after it.

### New features

* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) `AsteriskConfigsVariables` gained two
  fields on the next free numbers, 7 and 8, making the SIP trunk's transport a per-project choice instead
  of a property of the image:
  * `SipTrunkTransport sip_trunk_transport = 7` — `SIP_TRUNK_TRANSPORT_UNSPECIFIED` (0),
    `SIP_TRUNK_TRANSPORT_TLS` (1), `SIP_TRUNK_TRANSPORT_UDP` (2), `SIP_TRUNK_TRANSPORT_TCP` (3). Unset ==
    `UNSPECIFIED` == `TLS`: **the zero value is the encrypted one**, so a caller that says nothing gets an
    encrypted trunk. The field takes no `optional` keyword, because an enum whose zero IS a documented
    `*_UNSPECIFIED` sentinel already carries the third state.
  * `optional string sip_trunk_source_cidr = 8` — the source address or CIDR the carrier sends from, e.g.
    `203.0.113.7/32`. REQUIRED when the transport is `UDP` or `TCP`, where the trunk is matched by source
    address rather than authenticated by a certificate, and ignored otherwise. A hostname is refused with
    `INVALID_ARGUMENT`: Asterisk drops a `type=identify` section whose `match=` does not resolve, and it
    does so silently, so an unresolvable name would read as a working trunk that never matches an inbound
    call. This one DOES take `optional`, so a validator can tell an explicit empty CIDR from nothing sent
    and refuse each by name, and so an `update_mask` can CLEAR it rather than assign `""`.

  Both are additive. An 8.x server decoding a 9.0.0 request skips them as unknown fields.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) New service `Softphones` in the new file
  `ondewo/vtsi/softphones.proto` (unreleased, in development): SIP accounts on a project's Asterisk for
  humans using a softphone such as Zoiper, each with its OWN SIP credentials and never one of the
  `ondewo000N` container accounts. Eleven RPCs:
  * accounts: `CreateSoftphoneAccount`, `GetSoftphoneAccount` (`field_mask`), `UpdateSoftphoneAccount`
    (required `update_mask`; updatable paths `display_name`, `transport_security`, `enabled`,
    `max_contacts`, `labels`, `allowed_destinations`), `DeleteSoftphoneAccount`, `ListSoftphoneAccounts`
    (structured `SoftphoneAccountFilter` by transport security, enabled, labels, display-name and
    SIP-username substring and certificate-expiry window; `field_mask`; `page_size` / `page_token`;
    `SoftphoneAccountSorting`) and `RotateSoftphoneCredentials`;
  * certificates: `ListSoftphoneCertificates` (per account or per project, filtered by status and expiry
    window), `GetSoftphoneCertificate` and `RevokeSoftphoneCertificate`;
  * provisioning: `GetSoftphoneProvisioning`, returning server, port, TLS transport, outbound proxy, SIP
    identity, mandatory SDES-SRTP, codecs (`opus`, `alaw`, `ulaw`), the server CA to trust, the fingerprint
    of the client certificate to import and step-by-step Zoiper 5 instructions.

  `SoftphoneTransportSecurity` chooses per account between `CLIENT_CERTIFICATE` (mutual TLS on the
  project's internal TLS port, with a client certificate issued by a per-project SOFTPHONE CA) and
  `SERVER_TLS_ONLY` (the external TLS port, SIP digest only, for Zoiper editions without client-certificate
  support); the zero value means `CLIENT_CERTIFICATE`. **Secrets are returned exactly once**: the SIP
  password and the password-protected PKCS#12 bundle with the private key appear only in the
  `CreateSoftphoneAccount` and `RotateSoftphoneCredentials` responses (`SoftphoneCredentials`). Get, List
  and provisioning carry public material only (certificate PEM, CA PEM, SHA-256 fingerprint, serial,
  validity, status); a lost key or password is recovered by rotating it. Six new fields carry the
  `optional` keyword and are declared in `presence/expected_optional.txt`: `SoftphoneAccount.enabled`,
  `SoftphoneAccountFilter.enabled`, `SoftphoneAccountSorting.sorting_field` and `.sorting_mode`, and
  `page_token` of both list requests. Purely additive: no existing message, field or RPC changes.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) Answering machine detection (AMD) for
  pooled persistent callers: `VoiceInteractionConfig.answering_machine_detection_config = 4` of the new
  message `AnsweringMachineDetectionConfig`, with the enums `AmdAction` (`AMD_ACTION_UNSPECIFIED`,
  `HANG_UP`, `DETECT_ONLY`, `LEAVE_VOICE_MESSAGE`) and `AmdSensitivity` (`AMD_SENSITIVITY_UNSPECIFIED`, `LOW`, `MEDIUM`, `HIGH`).
  Its nineteen singular fields carry the `optional` keyword (unset = the CSI container default, documented
  per field together with its valid range) and are declared in `presence/expected_optional.txt`; the two
  phrase lists are `repeated string`. Defaults: `active` false, `action` `HANG_UP`, `sensitivity` `LOW`,
  hang up on fax and network announcements, not on IVRs and call screening. A listener or a one-shot
  caller carrying the config is rejected with `INVALID_ARGUMENT`. `LEAVE_VOICE_MESSAGE` speaks the
  fulfillment of `voice_message_intent` (default: the welcome intent) once after the beep, waiting at most
  `voice_message_max_beep_wait_ms` (default 10000, 0 - 30000), and hangs up when it finished playing or at
  `voice_message_timeout_ms` after the verdict (default 30000, 5000 - 120000); a fax never gets a message.
  `keyword_detection_active` and `cadence_detection_active` (both default true) switch those detectors off
  next to `beep_detection_active`. `HANG_UP` stays the default because leaving a recorded message on a
  consumer's mailbox for marketing is consent-bound (e.g. § 7 UWG in Germany).
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) `Call` gained
  `optional bool redial_recommended = 19` and `optional string redial_reason = 20`, set only when AMD ended
  the call (`answering_machine` and `network_announcement` hung up on without a voice message recommend a
  redial; a left voice message and `fax` do not), and
  `optional string answering_machine_detection_end_description = 21`, the description of the call's
  terminal `OUTGOING_CALL_FINISHED` status (one of the four AMD descriptions documented on the field). The AMD
  verdict, cause and confidence of a call are read from the existing `Call.sip_status.amd_result`, so they
  need no field of their own. No call is redialled automatically.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) `AsteriskConfigsVariables` gained two fields
  that make verifying the carrier's TLS certificate a per-project choice:
  * `optional string sip_trunk_ca_certificates_pem = 9` — the PEM bundle of the CA certificate(s) the
    carrier's TLS certificate chains to. Refused with `INVALID_ARGUMENT` for anything other than unexpired CA
    certificates (a private key in particular). Public data, not a secret.
  * `optional bool sip_trunk_verify_server = 10` — default false. Asterisk verifies the carrier's certificate
    chain and host name (`verify_server=yes`) only when this is true AND a CA bundle is given; true without a
    bundle is refused with `INVALID_ARGUMENT`. A bundle stored with verification off changes nothing on the
    trunk, so it can be staged before verification is switched on.

  Both apply only to the TLS trunk transport (a bundle, or verification switched on, is refused on a UDP or
  TCP trunk). Declared in `presence/expected_optional.txt`; purely additive.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) New service `Campaigns` in the new file
  `ondewo/vtsi/campaigns.proto`: a CAMPAIGN is a named set of outbound calls that VTSI places while keeping
  at most `max_parallel_calls` of them running at the same time (100 callers with `max_parallel_calls = 10`
  means at most 10 calls are set up or connected at any moment; the next starts when one ends).
  * CRUD: `CreateCampaign`, `GetCampaign`, `UpdateCampaign` (required `update_mask`; updatable paths
    `display_name`, `max_parallel_calls`, `max_attempts`, `retry_delay`, in every state), `DeleteCampaign`
    and `ListCampaigns` (`CampaignFilter` by state, display-name substring or exact display name;
    `page_size` / `page_token`).
  * Lifecycle: `StartCampaign`, `StopCampaign` (no new call is started, running calls finish),
    `HardStopCampaign` (running calls are hung up immediately; `HARD_STOPPED` only once every hang-up is
    confirmed) and `ResumeCampaign`. States: `CREATED`, `RUNNING`, `STOPPING`, `STOPPED`,
    `HARD_STOPPING`, `HARD_STOPPED`, `COMPLETED`.
  * Progress: `GetCampaignStatistics` (`CampaignStatistics`: `total`, `not_started`, `in_progress`,
    `retry_pending`, `completed`, `failed`, `cancelled`, `total_attempts`, `calls_retried`,
    `scheduled_not_due`, `progress_percent`) and `ListCampaignCalls` (`CampaignCall` with its state, SIP
    status type and description, attempts and, on request, the `attempt_history`).
  * Retries: `max_attempts` per campaign (default 1 = no retry, at most 10) and `retry_delay` (default
    60 s). A call counts as failed only after its last attempt; a failure that cannot succeed by repetition
    is never retried.
  * Names: resource name `projects/<project_uuid>/campaigns/<campaign_uuid>`; an empty `display_name`
    becomes `campaign-<campaign_uuid>`. Display names are unique per project, so every single-campaign RPC
    takes either the resource name or a `CampaignDisplayName`.
  * `StreamCampaignStatus`: a server-streaming snapshot of the project's campaigns followed by every change,
    optionally including campaign calls.

  Errors of the new RPCs are gRPC status codes, never `error_message` fields. Two new fields carry the
  `optional` keyword (`page_token` of `ListCampaignsRequest` and `ListCampaignCallsRequest`).
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) Two new `Calls` RPCs add callers to a
  campaign instead of starting them: `AddCallersToCampaign` (`AddCallersToCampaignRequest` /
  `AddCallersToCampaignResponse`) and `AddScheduledCallersToCampaign` (`AddScheduledCallersToCampaignRequest`
  / `AddScheduledCallersToCampaignResponse`). Each request carries a REQUIRED `CampaignAssignment
  campaign_assignment`: an existing campaign (by resource name or display name) or a new one (`new_campaign`),
  stored atomically, with `CampaignStartMode` choosing whether the campaign starts. The responses carry the
  `Campaign` and the created `campaign_call_names` (the scheduled variant also the
  `scheduled_caller_responses`), and `ScheduledCaller` gained `string campaign_name = 12`. `StartCallers` and
  `StartScheduledCallers` are unchanged against 8.7.x.
  Development builds of 9.0.0 carried the assignment as field 3 of `StartCallersRequest` /
  `StartScheduledCallersRequest` (and the campaign result as fields 4-5 / 3-4 of their responses). Those
  numbers and names are now `reserved`, and a server refuses a `StartCallers` / `StartScheduledCallers`
  request that still carries field 3 with `INVALID_ARGUMENT` instead of starting every caller.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) `AsteriskConfigsVariables` gained
  `repeated string softphone_permit_cidrs = 11`: the source allow-list (IPv4/IPv6 CIDRs) of the project's
  softphone accounts on both TLS ports, i.e. of the external TLS port for softphones. Empty means the
  server's `ONDEWO_VTSI_ASTERISK_SOFTPHONE_PERMIT_CIDRS` (default: the private networks); that server value
  is a ceiling a project can only narrow, and an entry outside it is refused with `INVALID_ARGUMENT`.
  `CreateSoftphoneAccount` and `UpdateSoftphoneAccount` document it.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) Three status streams on `Calls`:
  `StreamCallerStatus`, `StreamListenerStatus` and `StreamScheduledCallerStatus`, each sending a snapshot
  and then every changed `CallResourceStatus` (call, active flag, SIP status type and description, times,
  phone number, scheduled-caller state and campaign) in a `StreamCallResourceStatusResponse`.
* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) New service `Events` in the new file
  `ondewo/vtsi/events.proto`: every key event and status change of VTSI is one value of the new enum
  `VtsiEvent` (calls 1xx, callers 2xx, listeners 3xx, scheduled callers 4xx, campaigns 5xx, VTSI projects
  6xx, Asterisk 7xx, softphone accounts 8xx, the event system itself 9xx; 600 is reserved), delivered as a
  `VtsiEventMessage`.
  * Event subscriptions per project (which events, optionally narrowed by resource-name prefixes and
    campaign names, go to which webhooks): `CreateVtsiEventSubscription`, `GetVtsiEventSubscription`,
    `UpdateVtsiEventSubscription`, `DeleteVtsiEventSubscription`, `ListVtsiEventSubscriptions`.
  * Webhooks per project (an http(s) URL, `POST` or `PUT`, optional custom headers, a timeout):
    `CreateWebhook`, `GetWebhook`, `UpdateWebhook`, `DeleteWebhook`, `ListWebhooks` and `TestWebhook`.
    **Custom header values are write-only**: every RPC returns them as `********`, and an update that sends
    the mask keeps the stored value. Webhook delivery is best effort: at most a few retried requests per
    event, kept in memory, dropped rather than slowing a call down; de-duplicate by `event_id`.
  * `SubscribeVtsiEvents`: a server stream of the project's events, selected by a stored subscription or an
    inline `VtsiEventFilter`, resumable with `resume_token` within the server's journal retention.

  Five new fields carry the `optional` keyword (`page_token` of both list requests,
  `SubscribeVtsiEventsRequest.resume_token`, `VtsiEventMessage.sip_status_type` and
  `.previous_sip_status_type`). No new field is an `optional bool`, because ngx-grpc cannot send `false`
  for one; switches are plain bools whose zero value is the safe default (`disabled`) or enums whose
  `*_UNSPECIFIED` value is the documented default.

* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) Client idempotency keys for the five
  batch-creating `Calls` RPCs: `string idempotency_key` on `StartCallersRequest` (field 4),
  `StartListenersRequest` (3), `StartScheduledCallersRequest` (4), `AddCallersToCampaignRequest` (4) and
  `AddScheduledCallersToCampaignRequest` (4). A client that retries after a timeout or `UNAVAILABLE` (when the
  first attempt may in fact have succeeded) sends the same key and gets the FIRST attempt's response back
  instead of a second batch, whichever server replica the retry reaches. The key is scoped to the project and
  the RPC and retained by the server for 24 hours by default; the same key with a different request is
  `INVALID_ARGUMENT`, a retry while the first attempt still runs is `ABORTED` (retry later), and a failed
  first attempt stores nothing. A replayed response carries no `common_services_config`. Empty = no
  deduplication, byte-for-byte the previous behaviour. The single-resource RPCs take no key: their request
  messages are also the ITEMS of the batch requests, where a key would have no meaning; send a batch of one.
  No `optional` keyword (the empty string already means "no key"), so `presence/expected_optional.txt` is
  unchanged.

### Compatibility

**Binary wire-compatible in BOTH directions. Source-breaking in every language. This is a MAJOR release
because of the second sentence, not the first.** For a code-generating IDL the published contract is the
generated symbol set, not the encoding, and this release removes `sip_conf_file_string` and its four
accessor spellings from five languages at once.

What that buys the operator: no coordinated deploy, no client-before-server ordering, and no rewrite of any
stored protobuf payload. Measured with `grpc_tools.protoc` and protobuf 7.35.1, compiling the 8.7.0 and
9.0.0 trees into two independent descriptor pools: an `AsteriskConfigsFiles` carrying the same text
serialises to the same 14 bytes under either name, each side parses the other's bytes and re-serialises them
byte-identically.

Two things are NOT compatible, and neither raises anything at runtime.

The JSON key moves. No `json_name` override is added, so `protoc` derives it from the field name and it goes
from `sipConfFileString` to `pjsipConfFileString`. Any consumer that goes through `MessageToJson`,
`ParseDict` or a hand-written JSON mapping must move with it. An override was considered and rejected: with
the protobuf pin, `[json_name = "sipConfFileString"]` makes `ParseDict({"pjsipConfFileString": ...})` FAIL
while the old key keeps working — it SWAPS the accepted key rather than widening it, which reinstates the
name that lies in the one surface a human reads.

The presence change has a MIRROR, and there is no runtime detector for it. A 9.0.0 client that explicitly
sets one of the eleven fields to its default now puts bytes on the wire where 8.7.0 put none (`b''` becomes
`b'\x08\x00'` for a `bool`, and `MessageToJson` goes from `{}` to `{"activate_s2t": false}`). The mirror is
the risk: an 8.7.0 client that explicitly sets the default still sends NOTHING, and a 9.0.0 server reads
that as unset. The two cases are identical on the wire, so no server-side check can separate them —
regenerate a client against 9.0.0 before relying on an explicit default reaching the server as an explicit
default. For the same reason, a round trip of a 9.0.0 message through an un-regenerated SDK silently DROPS
presence, which is why all five clients are regenerated in one cycle.

One trap for anyone writing a test against this. On an 8.7.0 message `HasField` on these eleven fields
RAISES `ValueError: Field ... does not have presence` rather than returning `False`, so a test that probes
with `HasField` crashes on exactly the messages it is meant to classify. The detection signal is
`FieldDescriptor.has_presence`.

Three vendored API submodule pins do not move in this release: `ondewo-nlu-api` stays at `tags/7.1.0`,
`ondewo-s2t-api` at `tags/7.5.0` and `ondewo-t2s-api` at `tags/6.6.0`. `ondewo-sip-api` moves from
`tags/5.4.0` to the answering-machine-detection commit `33d03678221f6bef6bfa1216c5808f99b7d8573d`
(a development pin, replaced by the released sip-api tag at release). That sip-api change is purely
additive against 5.4.0 (`SipStatus.StatusType.OUTGOING_CALL_ANSWERING_MACHINE_DETECTED = 22`, non-terminal;
`AnsweringMachineDetectionResult`, `SipStatus.amd_result`, `SipEndCallRequest.end_reason` and `amd_result`,
the RPC `SipReportAnsweringMachineDetected`), and it means the vendored-proto
lockstep rule DOES fire: a consumer installing `ondewo-vtsi-client` next to `ondewo-sip-client` must take
the sip client generated from the same sip-api commit, or the last installed copy of `ondewo/sip` wins.

**Campaign enrollment fails closed during a rolling update.** A server replica that predates
`AddCallersToCampaign` / `AddScheduledCallersToCampaign` answers them with `UNIMPLEMENTED` and starts
nothing, so a campaign can never be dialled all at once by an old replica. Clients must NOT fall back to
`StartCallers` on `UNIMPLEMENTED`; retry later. The new `Campaigns` and `Events` services and the three
status streams answer `UNIMPLEMENTED` on an older replica too, which is harmless.

**Idempotency keys are ignored by an older server replica.** A replica that predates `idempotency_key`
skips it as an unknown field and runs the request, i.e. a retry reaching it during a rolling update behaves as
before this release. Deduplication is guaranteed once every replica runs a server that reads the key.

**Server behaviour documented in this release (no wire change).** `BaseServiceConfig.grpc_cert` is now
REQUIRED for the S2T, NLU and T2S configs of a call unless the VTSI server runs with
`ONDEWO_VTSI_ALLOW_INSECURE_UPSTREAM=True` (lab and CI only); an empty value is otherwise refused with
`FAILED_PRECONDITION` (`UPSTREAM_TLS_REQUIRED`). `UpdateWebhook` documents that moving a webhook's `url` to
another origin (scheme, host or port) while custom headers are stored requires re-sending `custom_headers`
with their real values (or an empty map) in the same request; the stored values never follow the url to a
new origin.

### Build

* [[OND233-367]](https://ondewo.atlassian.net/browse/OND233-367) `make presence_check` works out of the box.
  It needed `PRESENCE_PY` pointing at a python with `grpcio-tools`, and a plain `python3` without it failed
  with exit 2. With `PRESENCE_PY` unset it now runs through a `uv run --no-project` runner with a pinned
  `grpcio-tools`; `PRESENCE_PY` still overrides it. On a machine without index access, warm uv's cache once or
  set `PRESENCE_PY`.

*****************

## Release ONDEWO VTSI API 8.7.0

### Improvements

* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Re-vendored against
  [ondewo-nlu-api 7.1.0](https://github.com/ondewo/ondewo-nlu-api/releases/tag/7.1.0) (was 7.0.0) and
  [ondewo-s2t-api 7.5.0](https://github.com/ondewo/ondewo-s2t-api/releases/tag/7.5.0) (was 7.4.0).
  `ondewo/vtsi/**` is **unchanged**: no VTSI message, field or RPC moves in this release, so a client
  built against 8.6.0 stays wire-compatible with one built against 8.7.0.
* What grows is the vendored surface this API re-exports, and exactly two files changed:
  `ondewo/s2t/speech-to-text.proto` gains the `VadMethod` and `TsdMethod` enums and the `Silero` and
  `WespeakerTsd` messages (voice-activity and turn-shift detection configuration), and
  `ondewo/nlu/rag.proto` gains `RagCrawlerIncrementalConfig`.
* **The rag change is wire-compatible but is NOT purely additive, and the distinction is worth
  stating rather than assuming.** Four fields of `RagCrawlerFilters` are re-declared with
  `[deprecated = true]` — `allow_internal_links` (3), `allow_social_media_links` (5),
  `allowed_paths` (8) and `disallowed_paths` (9). Every field NUMBER, name and type is preserved, so
  nothing on the wire changes and no number is reused; generated code gains deprecation markers only.
  The two path lists are superseded by `allowed_regex` / `disallowed_regex`, and the two booleans are
  documented upstream as having never had any effect.

### Why this release exists

* The consumers that vendor these protos alongside a service client — `ondewo-vtsi-client` next to
  `ondewo-nlu-client` and `ondewo-s2t-client` — must be regenerated from the SAME API versions those
  clients ship. Measured against the 8.6.0 client wheel: its `ondewo/nlu` tree differs from
  `ondewo-nlu-client` 7.1.2 in exactly `rag_pb2.py` / `.pyi`, and its `ondewo/s2t` tree differs from
  `ondewo-s2t-client` 7.5.0 in exactly `speech_to_text_pb2.py` / `.pyi`. Those are the same module
  paths in one site-packages, so the skew is resolved by install order rather than by an error.

*****************

## Release ONDEWO VTSI API 8.6.0

### Improvements

* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Added the field `update_mask` to
  `UpdateVtsiProjectRequest`, a `google.protobuf.FieldMask` on the next free number, 2. Without it a field
  that has once been set can never be unset: `UpdateVtsiProject` merges the incoming project additively, so a
  scalar sent at its proto3 default is indistinguishable from a scalar the caller never mentioned and the
  stored value survives. The worked case is `AsteriskConfigs.asterisk_version` — once a project is pinned to
  an Asterisk image tag it stays pinned, which defeats the deploy-time fallback that is the whole point of
  leaving the field unset. The same mechanism blocked resetting `display_name`, `max_callers` and
  `max_listeners`, and clearing `nlu_agent_names`. Paths are field paths within `vtsi_project` and carry no
  leading `vtsi_project.` prefix, so the mask can be handed straight to the standard `FieldMask` merge
  helpers, which take paths relative to the message being merged. A path in the mask but absent from
  `vtsi_project` means CLEAR; a path absent from the mask leaves the field untouched; an unset or empty mask
  keeps the additive merge every earlier release performed.
* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Made
  `CsiVtsiConfig.activate_control_messages` `optional`. As a presence-less `bool` it read back as `false`
  whether the caller had switched control messages off or had said nothing at all, while the server's own
  default for the setting is on — so a caller that never mentioned control messages silently disabled them.
  `optional` adds the third state: unset now means "no preference expressed, keep the server default", which
  is a different instruction from an explicit `false`. It also makes an explicit `false` expressible for the
  first time, since a presence-less `false` puts no bytes on the wire at all.

### Compatibility

Wire-compatible in both directions; this is a MINOR release.

`update_mask` is additive. It takes field number 2 in a message that previously ended at 1, so an 8.5.0
server decoding an 8.6.0 request skips it as an unknown field and applies the additive merge it always
applied, and an 8.6.0 server reading an 8.5.0 request sees an empty mask, which means exactly that same
additive merge. A request that sends no mask is byte-identical to the 8.5.0 request. Because an older server
ignores the mask rather than rejecting it, a client must not send one until the server it talks to honours
it — a silently ignored mask reads as a successful clear that did not happen.

`activate_control_messages` keeps field number 6 and wire type `bool`; `optional` only adds explicit
presence, compiling to a synthetic one-member oneof (`_activate_control_messages`) that exists in the
descriptor and not on the wire. The encoding of `true` is byte-for-byte what 8.5.0 emitted. One asymmetry is
worth stating, because it constrains the server: an 8.5.0 client setting the field to `false` serialises
nothing, so an 8.6.0 server sees it as unset and will apply its default rather than `false`. That
ambiguity is the pre-existing defect and is not introduced here, but it is the reason the field cannot be
read as a plain tri-state until the clients are on 8.6.0. Note also that ngx-grpc flattens `optional` and
writes only truthy values, so an Angular caller can send `true` or nothing, but not `false`.

*****************

## Release ONDEWO VTSI API 8.5.0

### Improvements

* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Gave `ScheduledCaller` a read and cancel
  surface. `StartScheduledCaller` and `StartScheduledCallers` created a named, persisted resource that no RPC
  could subsequently observe or withdraw, so a schedule that failed at fire time was — in the words of the
  server's own comment — "invisible to the client by construction". Three RPCs close that: `GetScheduledCaller`
  returns a single `ScheduledCaller`, matching `GetCaller` and `GetListener` in returning the bare resource
  rather than a wrapper; `ListScheduledCallers` pages a project's scheduled callers oldest `scheduled_time`
  first, with the same `page_token` / `next_page_token` contract as `ListCallers`, `ListListeners` and
  `ListCalls`; and `CancelScheduledCaller` withdraws one that has not fired yet.
* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Added `ScheduledCallerStatus`, the lifecycle
  of a scheduled caller: `PENDING`, `FIRING`, `DONE`, `FAILED`, `CANCELLED`. The members are prefixed
  (`SCHEDULED_CALLER_STATUS_*`) because proto3 enum members share the enclosing file's scope, matching
  `CallStatus` rather than the older unprefixed `CallView` and `CallType`.
* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Extended `ScheduledCaller` with six fields,
  numbers 6 to 11, leaving 1 to 5 byte-for-byte unchanged: `sip_caller_config` (the full caller configuration —
  field 3 `sip_config` carries only its `sip_base_config` half, so `callee_id` and `sip_headers` were dropped
  and the create response could not say who would be called), `status`, `vtsi_project_name`, `created_at`,
  `fired_at` and `error_message`. `created_at` and `fired_at` are message fields, which carry presence in
  proto3 without `optional`, so a pending row leaves `fired_at` unset rather than stamping epoch zero.
  `claimed_by` is deliberately **not** exposed: it is `<hostname>:<pid>` and would teach a tenant the server's
  internal topology while gaining them nothing.
* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Fixed the two RPC comments on
  `StartScheduledCaller` and `StartScheduledCallers`, which were the same copy-pasted sentence and wrong for
  the singular form.

### Compatibility

Wire-compatible in both directions. The three new RPCs are additive; the six new `ScheduledCaller` fields use
previously unused numbers, so an older client decoding a newer message skips them and a newer client reading an
older server sees the defaults. `ScheduledCallerStatus` carries a zero member,
`SCHEDULED_CALLER_STATUS_UNSPECIFIED`, so an old client decoding a new status is not left without a value.

*****************

## Release ONDEWO VTSI API 8.4.0

### Improvements

* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Added the field `next_page_token` to
  `ListCallersResponse`. `ListCallersRequest` has always accepted a `page_token`, but the response carried no
  way to return the next one, so `ListCallers` could not actually be paged: a caller either received the
  first page and had no means of asking for the second, or — worse — treated the first page as the complete
  set and silently under-counted. The field carries the same contract as its two siblings,
  `ListListenersResponse.next_page_token` and `ListCallsResponse.next_page_token`: a non-empty token means
  more results are available, and an empty token means the list is exhausted. It is a plain scalar rather
  than `optional` for exactly that reason — "no more results" and "no preference expressed" are not
  different states here, and the two sibling responses would otherwise disagree with this one on shape.
  Adding field number 2 to a message that previously ended at 1 is wire-compatible: an older client decoding
  a newer response skips the unknown field, and a newer client reading an older server sees the empty default,
  which is the correct "no further pages" answer

*****************

## Release ONDEWO VTSI API 8.3.0

### Improvements

* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Upgrade to ONDEWO NLU API [7.0.0](https://github.com/ondewo/ondewo-nlu-api/releases/7.0.0), ONDEWO S2T API [7.4.0](https://github.com/ondewo/ondewo-s2t-api/releases/7.4.0), ONDEWO T2S API [6.6.0](https://github.com/ondewo/ondewo-t2s-api/releases/6.6.0) and ONDEWO SIP API [5.4.0](https://github.com/ondewo/ondewo-sip-api/releases/5.4.0)
* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Added `ondewo/vtsi/logs.proto` for container log capture and streaming
* [[OND211-2418]](https://ondewo.atlassian.net/browse/OND211-2418) Added the optional field `asterisk_version` to
  `AsteriskConfigs`. It carries the docker image tag of the ONDEWO Asterisk image a VTSI project should start
  (e.g. `alpine-3.18-18.20.2`), so the Asterisk version becomes a per-project setting instead of a server-wide one.
  The field is explicitly `optional`: leaving it unset keeps the server default
  (`ONDEWO_VTSI_ASTERISK_IMAGE_TAG`), while an empty string is rejected rather than silently treated as unset
* [[OND235-105]](https://ondewo.atlassian.net/browse/OND235-105) Added `VoiceInteractionConfig` with
  `TurnDetectionConfig`, `InterruptionHandlingConfig`, `ResponseTimingConfig` and `SoftTimeoutConfig`
  to `CommonServicesConfig` for fine-granular per-call configuration of turn detection,
  interruption (barge-in) handling and response timing

*****************

## Release ONDEWO VTSI API 8.2.0

### Improvements

* [[OND233-373]](https://ondewo.atlassian.net/browse/OND233-373) Upgrade to ONDEWO NLU API [6.7.0](https://github.com/ondewo/ondewo-nlu-api/releases/6.7.0), ONDEWO S2T API [7.2.0](https://github.com/ondewo/ondewo-s2t-api/releases/7.2.0) and ONDEWO T2S API [6.2.0](https://github.com/ondewo/ondewo-t2s-api/releases/6.2.0)

*****************

## Release ONDEWO VTSI API 8.1.0

### Improvements

* [[OND233-372]](https://ondewo.atlassian.net/browse/OND233-372) Upgrade to ONDEWO S2T API [6.1.0](https://github.com/ondewo/ondewo-s2t-api/releases/6.1.0)

*****************

## Release ONDEWO VTSI API 8.0.0

### Improvements

* [[OND233-372]](https://ondewo.atlassian.net/browse/OND233-372) Upgrade to ONDEWO NLU API [6.0.0](https://github.com/ondewo/ondewo-nlu-api/releases/6.0.0), ONDEWO S2T API [6.0.0](https://github.com/ondewo/ondewo-s2t-api/releases/6.0.0) and ONDEWO T2S API [6.0.0](https://github.com/ondewo/ondewo-t2s-api/releases/6.0.0) and ONDEWO SIP API [5.2.0](https://github.com/ondewo/ondewo-t2s-api/releases/5.2.0) libraries

*****************

## Release ONDEWO VTSI API 7.0.0

### Improvements

* [[OND233-366]](https://ondewo.atlassian.net/browse/OND233-366) Upgrade to ONDEWO NLU
  API [4.7.0](https://github.com/ondewo/ondewo-nlu-api/releases/4.7.0), ONDEWO S2T
  API [5.4.0](https://github.com/ondewo/ondewo-s2t-api/releases/5.4.0) and ONDEWO T2S API
  [5.3.0](https://github.com/ondewo/ondewo-t2s-api/releases/5.3.0) libraries

*****************

## Release ONDEWO VTSI API 6.9.0

### Improvements

* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added `CallStatus`, `StopListener`, `StopListeners`,
  `StopCaller` and `StopCallers` for improved control over the Listeners and Callers
* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added `CallView` to `ListCallersRequest`,
  `ListListenersRequest`, `GetCallerRequest` and `GetListenerRequest` for better control of data transfer amounts
* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added platform to choose the NLU platform in the
  `NluVtsiConfig` for `DetectIntent` response generation

*****************

## Release ONDEWO VTSI API 6.8.0

### Improvements

* [[OND211-2162]](https://ondewo.atlassian.net/browse/OND211-2162) Updated to ONDEWO NLU
  API [5.0.0](https://github.com/ondewo/ondewo-nlu-api/releases/5.0.0)

*****************

## Release ONDEWO VTSI API 6.7.0

### Improvements

* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Updated dependencies to ONDEWO NLU
  API [4.9.0](https://github.com/ondewo/ondewo-nlu-api/releases/4.9.0), ONDEWO S2T
  API [5.6.0](https://github.com/ondewo/ondewo-s2t-api/releases/5.6.0) and ONDEWO T2S API
  [5.2.0](https://github.com/ondewo/ondewo-t2s-api/releases/5.2.0) and therefore removed `GetAudioFile`
  and `GetFullConversationAudioFile` from ONDEWO VTSI API since it is now
  in ONDEWO NLU API ([[OND21-2143]](https://ondewo.atlassian.net/browse/OND211-2143))
* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added `CallFilter` to improving monitoring capabilities
  and filtering with `ListCallsRequest`
* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added `deployed_callers` and `deployed_listeners`
  to `VtsiProject`

### Bug Fixes

* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) `TransferCallRequest` should not have a repeated field
  `transfer_id`

*****************

## Release ONDEWO VTSI API 6.6.0

### Improvements

* [[OND233-335]](https://ondewo.atlassian.net/browse/OND233-335) - Add `DeleteCallers`, `DeleteCaller`, `DeleteListener`
  and
  `DeleteListeners`. Also added `nlu_session_name` to `Call` and added `CallType.SCHEDULED_CALLER`.

*****************

## Release ONDEWO VTSI API 6.5.0

### Improvements

* [[OND233-333]](https://ondewo.atlassian.net/browse/OND233-333) - Add associated NLU agents in `VtsiProject` and in
  `ListVtsiProjects`

*****************

## Release ONDEWO VTSI API 6.4.0

### Improvements

* [[OND233-332]](https://ondewo.atlassian.net/browse/OND233-332) - Added `ListCallers`, `GetCaller`, `ListListeners` and
  `GetListener`

### Breaking changes

* [[OND233-332]](https://ondewo.atlassian.net/browse/OND233-332) - Renamed `GetCallInfo` and `ListCallInfos` methods to
  `GetCall` and `ListCalls`

*****************

## Release ONDEWO VTSI API 6.3.0

### Improvements

* [[OND233-331]](https://ondewo.atlassian.net/browse/OND233-331) - Added `ListVtsiProjects` to list VTSI projects incl.
  the capabilities to sorting and for different views

*****************

## Release ONDEWO VTSI API 6.2.0

### Improvements

* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Updated Sip API 5.0.0

*****************

## Release ONDEWO VTSI API 6.1.0

### Improvements

* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Updated Sip API

*****************

## Release ONDEWO VTSI API 6.0.0

### Improvements

* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Added `VtsiProjectStatus`
* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Use `Timestamp` instead of double

*****************

## Release ONDEWO VTSI API 5.0.0

### Improvements

* Synchronize API Client Versions

*****************

## Release ONDEWO VTSI API 4.0.0

### Improvements

* Adjusted `TransferCalls` and `TransferCallsRequest`
* Upgraded to NLU API 2.13.0

*****************

## Release ONDEWO VTSI API 3.0.0

### New features

* New VTSI API release 3.0.0
* [[OND211-2039]](https://ondewo.atlassian.net/browse/OND211-2039) - Automated Release Process
* [[OND211-2039]](https://ondewo.atlassian.net/browse/OND211-2039) - Added pre-commit hooks and adjusted files tot them

*****************

## Release ONDEWO VTSI API 2.3.0

### New features

Added endpoints for minio data retrieval

*****************

## Release ONDEWO VTSI API 2.2.0

### New features

CSI configs can be passed like Rabbit mq configs

## Release ONDEWO VTSI API 2.1.0

### New features

CSI configs can be passed like MINIO configs

*****************

## Release ONDEWO VTSI API 2.0.0

### New features

Adaptation to new s2t and t2s configs

*****************

## Release ONDEWO VTSI API 1.1.0

### New features

* ServiceConfig extended with grpc_cert field

*****************

## Release ONDEWO VTSI API 1.0.0

### New features

* First stable version

### Improvements

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

* [Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.4.0

### New Features

### Improvements

* Deleted unnecessary call logs
* New endpoint to start multiple calls added

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

[Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.3.1

### New Features

### Improvements

* Added sip prefix and name and passwords
* Changed timestamps and start/end times to doubles

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

[Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.3.0

### New Features

### Improvements

* Simplified the call initiation (no difference between listeners and callers)

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

* [Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.2.3

### New Features

### Improvements

* Updated license

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

* [Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.2.2

### New Features

### Improvements

* Updated README.

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

* [Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.2.1

### New Features

* Fixed license header.

### Improvements

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

* [Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.2.0

### New Features

* Move to GitHub!

### Improvements

* No longer closed source.

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

### Migration Guide

* [Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************

## Release ONDEWO VTSI API 0.1.0

### New Features

* Refactored individual project APIs into separate repos.

### Improvements

* Easier to develop independently.

### Bug fixes

### Breaking Changes

### Known issues not covered in this release

* Harder to install apis under one heading-- this will be addressed at a later date.

### Migration Guide

* [Replace submodule](https://stackoverflow.com/a/1260982/7756727) in the client.

*****************
