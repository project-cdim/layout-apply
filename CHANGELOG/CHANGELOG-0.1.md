# Changelog 0.1

## [0.1.1](https://github.com/project-cdim/layout-apply/compare/v0.1.0...v0.1.1) - 2025-09-29

The changes from v0.1.0 are as follows:

### Features

- Added information about the steps currently being executed to the information that can be referenced during IN_PROGRESS.

- Added support for migration procedures for work types "Service Start/Stop".

- Added a feature to publish messages to the Message broker when Layout Apply is completed.

### Breaking Changes

- Removed the "fields" option from the API for referencing Layout Apply status.

- Changed the returned information when the "fields" option is not specified in the API for obtaining Layout Apply status list.

### Other Changes

- Replaced the [`cdimlogger`](https://github.com/project-cdim/layout-apply/tree/v0.1.0/src/layoutapply/cdimlogger) library with Python's built-in logger.

- Added an error code and message for cases where the number of polling attempts after power ON/OFF exceeds the limit and Layout Apply fails.
