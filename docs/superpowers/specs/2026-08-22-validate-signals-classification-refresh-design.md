# Validate Signals Classification Refresh Design

**Date:** 2026-08-22
**Status:** Implemented and verified

Classification changes re-render only the latest batch with at least one
successful ticker. Fresh sessions render no result list. A failed later attempt
shows its immediate errors but does not replace the cached successful results.
Filtering is local; it never replays validation, submits work, or changes data.
