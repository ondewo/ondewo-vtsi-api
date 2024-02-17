# Release History

*****************

## Release ONDEWO VTSI API 6.9.0

## Improvements

* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added CallStatus, StopListener/s and StopCaller/s for
  improved control over the Listeners and Callers
* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added CallView to ListCallersRequest,
  ListListenersRequest, GetCallerRequest and GetListenerRequest for better control of data transfer amounts

*****************

## Release ONDEWO VTSI API 6.8.0

## Improvements

* [[OND211-2162]](https://ondewo.atlassian.net/browse/OND211-2162) Updated to NLU API 5.0.0

*****************

## Release ONDEWO VTSI API 6.7.0

## Improvements

* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Updated dependencies to apis nlu 4.9.0, s2t 5.6.0 and
  t2s 5.2.0 and therefore removed `GetAudioFile` and `GetFullConversationAudioFile` from ONDEWO VTSI API since it is now
  in ONDEWO NLU API ([[OND21-2143]](https://ondewo.atlassian.net/browse/OND211-2143))
* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added `CallFilter` to improving monitoring capabilities
  and filtering with `ListCallsRequest`
* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) Added `deployed_callers` and `deployed_listeners`
  to `VtsiProject`

## Bug Fixes

* [[OND233-341]](https://ondewo.atlassian.net/browse/OND233-341) `TransferCallRequest` should not have a repeated field
  `transfer_id`

*****************

## Release ONDEWO VTSI API 6.6.0

## Improvements

* [[OND233-335]](https://ondewo.atlassian.net/browse/OND233-335) - Add `DeleteCallers`, `DeleteCaller`, `DeleteListener`
  and
  `DeleteListeners`. Also added `nlu_session_name` to `Call` and added `CallType.SCHEDULED_CALLER`.

*****************

## Release ONDEWO VTSI API 6.5.0

## Improvements

* [[OND233-333]](https://ondewo.atlassian.net/browse/OND233-333) - Add associated NLU agents in `VtsiProject` and in
  `ListVtsiProjects`

*****************

## Release ONDEWO VTSI API 6.4.0

## Improvements

* [[OND233-332]](https://ondewo.atlassian.net/browse/OND233-332) - Added `ListCallers`, `GetCaller`, `ListListeners` and
  `GetListener`

## Breaking changes

* [[OND233-332]](https://ondewo.atlassian.net/browse/OND233-332) - Renamed `GetCallInfo` and `ListCallInfos` methods to
  `GetCall` and `ListCalls`

*****************

## Release ONDEWO VTSI API 6.3.0

## Improvements

* [[OND233-331]](https://ondewo.atlassian.net/browse/OND233-331) - Added `ListVtsiProjects` to list VTSI projects incl.
  the capabilities to sorting and for different views

*****************

## Release ONDEWO VTSI API 6.2.0

## Improvements

* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Updated Sip API 5.0.0

*****************

## Release ONDEWO VTSI API 6.1.0

## Improvements

* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Updated Sip API

*****************

## Release ONDEWO VTSI API 6.0.0

## Improvements

* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Added `VtsiProjectStatus`
* [[OND233-323]](https://ondewo.atlassian.net/browse/OND233-323) - Use `Timestamp` instead of double

*****************

## Release ONDEWO VTSI API 5.0.0

## Improvements

* Synchronize API Client Versions

*****************

## Release ONDEWO VTSI API 4.0.0

## Improvements

* Adjusted `TransferCalls` and `TransferCallsRequest`
* Upgraded to NLU API 2.13.0

*****************

## Release ONDEWO VTSI API 3.0.0

## New features

* New VTSI API release 3.0.0
* [[OND211-2039]](https://ondewo.atlassian.net/browse/OND211-2039) - Automated Release Process
* [[OND211-2039]](https://ondewo.atlassian.net/browse/OND211-2039) - Added pre-commit hooks and adjusted files tot them

*****************

## Release ONDEWO VTSI API 2.3.0

## New features

Added endpoints for minio data retrieval

*****************

## Release ONDEWO VTSI API 2.2.0

## New features

CSI configs can be passed like Rabbit mq configs

## Release ONDEWO VTSI API 2.1.0

## New features

CSI configs can be passed like MINIO configs

*****************

## Release ONDEWO VTSI API 2.0.0

## New features

Adaptation to new s2t and t2s configs

*****************

## Release ONDEWO VTSI API 1.1.0

## New features

* ServiceConfig extended with grpc_cert field

*****************

## Release ONDEWO VTSI API 1.0.0

## New features

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
