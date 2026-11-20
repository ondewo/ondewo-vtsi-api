# Warm intros in the ONDEWO VTSI API

This guide describes the warm intro of a WARM transfer. The generated reference of every message and field is
[index.md](index.md) (also `index.html`); this page explains how the pieces fit together. It covers ONDEWO VTSI API
**9.5.0**, built on ONDEWO SIP API 5.7.0 and ONDEWO NLU API 7.6.0.

A WARM transfer (`TransferCallRequest.mode = TRANSFER_MODE_WARM`) rings the target into the call and lets the bot
leave only once the target joined. With a **warm intro** an ONDEWO bot first talks to the target, while the caller
waits with the paused bot of the call:

1. It confirms a person is on the line (`ready_question`, answered by voice or `accept_dtmf`). This is the mailbox
   guard: nothing about the caller is said before it.
2. It briefs the target: who calls and why (`intro_prompt`, `{caller_name}`, `{topic}`, `{callee_name}`).
3. It asks whether the target accepts (`accept_question`, or the keys `accept_dtmf` / `decline_dtmf`).
4. On a decline it asks what to tell the caller (`decline_reason_question`).

An accepting target is joined, as in every WARM transfer. A declining, silent or unreachable target is hung up and
the call **stays with the bot**, which tells the caller (`caller_declined_message`, with the target's reason, or
`caller_unreachable_message`).

## Configuration: `WarmTransferConfig`

`WarmTransferConfig` (in `call_configs.proto`) can be set on four levels. Every scalar is `optional`; an unset
field inherits from the next level, the most specific level winning per field (protobuf `MergeFrom`):

| Level | Field |
| --- | --- |
| one transfer | `TransferCallRequest.warm_transfer_config = 9` (WARM only; with BLIND it is `INVALID_ARGUMENT`) |
| one call (listener, caller, campaign) | `VoiceInteractionConfig.warm_transfer_config = 6` |
| the project | `VtsiProject.warm_transfer_defaults = 22` |
| the deployment | the server's `ONDEWO_VTSI_WARM_TRANSFER_*` settings |
| the NLU agent (texts and the LLM service only) | `ondewo.nlu.Agent.warm_transfer_settings` |
| built in | the defaults below |

`enabled` unset at every level is `false`: a WARM transfer then behaves exactly as before 9.5.0. An NLU agent whose
warm transfer settings switch the intro off makes it unavailable, and `on_intro_unavailable` decides.

| Field | Default | Notes |
| --- | --- | --- |
| `enabled` | `false` | master switch |
| `intro_prompt` | template | TEMPLATE: the briefing with `{caller_name}` `{callee_name}` `{topic}` `{summary}`; LLM_SUMMARY: the LLM instruction; at most 4000 characters |
| `intro_text_source` | TEMPLATE (LLM_SUMMARY with phase B and an LLM service) | LLM_SUMMARY falls back to TEMPLATE when the LLM fails |
| `ready_question` | "Hier ist der digitale Assistent von {project}. Ich habe einen Anruf für Sie. Sind Sie am Apparat? Sagen Sie ja oder drücken Sie 1." | carries no personal data |
| `confirm_human_before_intro` | `true` | brief only after a ready answer |
| `accept_question` | "Möchten Sie das Gespräch übernehmen? Ja oder 1, nein oder 2." | |
| `decline_reason_question` | "Was darf ich dem Anrufer ausrichten?" | `""` = do not ask |
| `caller_declined_message` | "{callee_name} kann das Gespräch gerade nicht übernehmen und lässt ausrichten: {reason}" | without a reason, a variant without the clause |
| `caller_unreachable_message` | built in, `{callee_name}` | busy, no answer, no decision, hung up, intro unavailable |
| `accept_dtmf` / `decline_dtmf` | `1` / `2` | one of `0-9 * #`, different from each other |
| `decision_timeout_s` | 20 | 5 - 60, from a question to the decision |
| `max_intro_duration_s` | 90 | 30 - 300, from the target's answer to the decision |
| `callee_display_name` | resolved, see below | at most 128 characters |
| `callee_description` | resolved, see below | at most 512 characters |
| `on_intro_unavailable` | `CONNECT_WITHOUT_INTRO` | or `RETURN_TO_CALLER` |
| `apply_to_bot_transfers` | `false` | call and project level only |
| `caller_disclosure_message` | none | spoken to the caller first |
| `caller_hold_message` | none | spoken to the caller while the intro runs |
| `caller_reassure_interval_s` | 0 (never) | 0 or 15 - 120: repeat the hold message |
| `caller_accepted_message` | none | spoken to the caller before the target joins, `{callee_name}`; the target does not hear it |
| `caller_hold_music` | `false` | phase B |
| `llm_ccai_service_name` | the agent's, then the project's first LLM service | phase B |
| `store_intro_audio` | `false` | whether the intro bot's NLU session stores audio |
| `intro_listener_names` | any free listener | project level only, at most 50 |

**Phase B.** LLM_SUMMARY, `caller_hold_music` and `llm_ccai_service_name` are refused with `FAILED_PRECONDITION`
`reason=phase-b-not-enabled` until the deployment enables them. `VtsiProject.feature_availability.warm_intro_phase_b`
says whether it has.

**Validation.** A value outside its range, an unknown placeholder, SIP markup (`<SIP:`) in a text, or a field on a
level it does not belong to is refused with `INVALID_ARGUMENT` naming the field. `enabled=true` while the deployment
switch `ONDEWO_VTSI_WARM_TRANSFER_ENABLED` is off is refused with `FAILED_PRECONDITION` `reason=warm-intro-disabled`,
also on `UpdateVtsiProject`.

### Who the target is

`{callee_name}` and the briefing's description of the target resolve from the first non-empty of:

1. `WarmTransferConfig.callee_display_name` / `callee_description` of the transfer;
2. the target softphone account's `display_name` / `description` (`SoftphoneAccount.description = 22`, new);
3. `VtsiProject.transfer_target_directory = 25`, keyed by the E.164 number or the softphone account's
   `sip_username` (at most 200 entries; a phone number key must pass `transfer_phone_number_allowlist`).

That is how the bot's own handover to a target names the right person.

### Who the caller is and why they call

`{caller_name}` and `{topic}` are resolved by the ONDEWO NLU from the caller's SIP context and the session's
parameters, never from free caller speech. Without a name the briefing says "Ein Anrufer". The caller's name is
spoken to the target only after the ready answer.

## Starting a warm intro

**By an operator or an application:** `Calls.TransferCall` with `mode = TRANSFER_MODE_WARM` and a human target
(`CallTarget.phone_number` or `CallTarget.softphone_account_name`), where the effective config is enabled. It answers
**`TRANSFER_OUTCOME_PENDING`**; the final outcome arrives in `Call.last_transfer` and the events below. Authorization
and idempotency (`request_id`) are those of `TransferCall`; a repeat with the same `request_id` but a different
`warm_transfer_config` is `INVALID_ARGUMENT` `reason=request-id-conflict`.

**By the bot:** with `apply_to_bot_transfers` on the call or project level, the bot's own transfer to a human (an NLU
answer's transfer or human handover) is handed to VTSI instead of being sent by the bot, and VTSI runs it as a WARM
transfer with an intro. A bot transfer to anything else is sent as before.

### Preconditions

Checked before anything rings; each refusal is a gRPC status with `reason=<token>` and the call is untouched:

| Refusal | Reason |
| --- | --- |
| `INVALID_ARGUMENT` | `warm-intro-target-not-human`: a listener, the listener queue or an IVR menu as the target |
| `FAILED_PRECONDITION` | `warm-intro-disabled`: the deployment switch is off |
| `FAILED_PRECONDITION` | `asterisk-not-local`: the project's Asterisk is not run by this server |
| `FAILED_PRECONDITION` | `no-nlu-session`: the call has no live NLU session |
| `FAILED_PRECONDITION` | `warm-intro-needs-listener`: the project has no listener to run the intro |
| `FAILED_PRECONDITION` | `warm-intro-needs-session-from-sip-context`: the listeners do not take their NLU session from the SIP context |
| `FAILED_PRECONDITION` | `warm-intro-cross-project`: the listeners use another NLU project than the call |
| `FAILED_PRECONDITION` | `warm-intro-notice-unsupported`: the call's SIP container cannot hand the outcome to the caller's bot |
| `FAILED_PRECONDITION` | `call-control-disabled`: the deployment has no call-control key |
| `FAILED_PRECONDITION` | `phase-b-not-enabled`: a phase-B field while phase B is off |

`VtsiProject.feature_availability.warm_intro` (`WarmIntroAvailability`) reports the project-wide ones up front:
`AVAILABLE`, `DISABLED_BY_DEPLOYMENT`, `NEEDS_LOCAL_ASTERISK`, `NEEDS_LISTENER`, `NEEDS_CALL_CONTROL_KEY`.

### Capacity

The intro bot is a free listener of the project, reached through the listener queue. A warm intro never takes the
last ready listener: when only the reserved number of listeners is ready, the intro is unavailable. With
`intro_listener_names` (project level) the intro bots come from a dedicated pool instead. A project with pooled
callers only cannot run warm intros.

## Outcomes

| `TransferOutcome` | When | The call |
| --- | --- | --- |
| `TRANSFER_OUTCOME_ACCEPTED` | the target accepted and joined | the bot leaves |
| `TRANSFER_OUTCOME_DECLINED` (9) | the target declined | stays with the bot, which tells the caller |
| `TRANSFER_OUTCOME_NO_DECISION` (10) | the target answered but did not decide in time | stays with the bot |
| `TRANSFER_OUTCOME_TARGET_UNAVAILABLE` (11) | answered but gone: hung up during the intro, a mailbox suspected | stays with the bot |
| `TRANSFER_OUTCOME_INTRO_UNAVAILABLE` (12) | the intro could not run and `on_intro_unavailable = RETURN_TO_CALLER` | stays with the bot |
| `TRANSFER_OUTCOME_TIMEOUT`, ... | busy, no answer, unreachable: as before 9.5.0 | stays with the bot |

With `CONNECT_WITHOUT_INTRO` (the default) an intro that cannot run joins the target directly, exactly as a WARM
transfer without an intro; `warm_intro.intro_started` is then `false` and `warm_intro.cause` says why.

`CallTransferRecord` (in `Call.last_transfer`) gains:

- `warm_intro = 7` (`WarmIntroRecord`): `intro_id`, `decision`, `decided_by` (DTMF / SPEECH / TIMEOUT),
  `decline_reason_present`, `intro_call_name` (the intro bot's call, labelled `{"purpose": "warm_intro"}`),
  `ring_duration`, `intro_duration`, `text_source`, `text_fell_back`, `cause`, `notice_delivered` and
  `intro_started`. It holds **no** intro text and **no** reason text.
- `effective_warm_transfer_config = 8`: the resolved configuration, for support. It holds configuration texts only.

## Events

| Event | When |
| --- | --- |
| `VTSI_EVENT_CALL_WARM_INTRO_STARTED = 124` | the target answered and the intro bot greets it |
| `VTSI_EVENT_CALL_WARM_INTRO_ACCEPTED = 125` | accepted; `VTSI_EVENT_CALL_TRANSFERRED = 106` follows on join |
| `VTSI_EVENT_CALL_WARM_INTRO_DECLINED = 126` | declined |
| `VTSI_EVENT_CALL_WARM_INTRO_NO_DECISION = 127` | no decision in time |
| `VTSI_EVENT_CALL_WARM_INTRO_TARGET_UNAVAILABLE = 128` | `cause=voicemail-suspected`, `target-hung-up` or `intro-unavailable` |
| `VTSI_EVENT_CALL_WARM_TRANSFER_OUTCOME_NOTICE_UNDELIVERED = 129` | WARNING: the outcome could not be handed to the caller's bot (`reason`); `warm_intro.notice_delivered=false` |

Attributes of 124 to 128: `intro_id`, `target_kind`, `text_source`, `decided_by`, `reason_present`, `intro_ms` and
`cause`. A skipped intro adds `intro_skipped_reason` to event 106. No event carries an intro text, a decline reason
or a full phone number.

## Security and privacy

- **Authorization.** `TransferCall` keeps its authorization (`PROJECT_DEVELOPER`, Keycloak `ENFORCE`); the project
  defaults and the transfer target directory need `PROJECT_DEVELOPER` like every project update.
- **No text leaves the intro.** The briefing and the target's decline reason exist only in the intro bot's NLU
  session (conversation retention). VTSI never receives the reason; it reaches the caller only as the bot's answer,
  normalised: SIP markup removed, at most 300 characters, digit runs of 12 or more masked.
- **Mailbox guard.** With `confirm_human_before_intro` (the default) nothing about the caller is said before a person
  answered the `ready_question`.
- **Audio.** `store_intro_audio` defaults to `false`.
- **Disclosure.** `caller_disclosure_message` is empty by default; the default texts are subject to legal review before
  a release.
