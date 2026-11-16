# Changelog 0.2
 
## [0.2.0](https://github.com/project-cdim/layout-apply/compare/v0.1.1...v0.2.0) - 2026-03-24
 
The changes from v0.1.1 are as follows:
 
### Breaking Changes
 
- Removal of support for migration procedures for work types "Service Start/Stop".
 
- Changed the format of the "gpu" option in the API for migration procedures creation request.
 
### Other Changes
 
- Reflecting improvements in the HW control API.
 
- Improved log output content.

## [0.2.1](https://github.com/project-cdim/layout-apply/compare/v0.2.0...v0.2.1) - 2026-11-04

The changes from v0.2.0 are as follows:

### Added

- Added separate persistence and retrieval for rollback execution status and results, including rollback resume handling.
- Added configurable intermediate database updates based on elapsed time or the number of completed procedures.

### Changed

- Updated the API `fields` query parameter to use `result` instead of `applyResult`, `rollbackResult`, and `resumeResult`.

### Improved

- Improved status and result handling across API, CLI, and database operations.
