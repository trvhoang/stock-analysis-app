# Validate Signals Classification Refresh Implementation Plan

**Goal:** Filter the latest successful Validate Signals results when classifications change.

### Task 1

- [x] Add AppTest proving one validation run persists results and a later
  classification change re-renders the cached list without another validation call.
- [x] Run RED focused page test.
- [x] Cache only nonempty successful batches; render that cache after every rerun.
- [x] Run GREEN page suite and compilation. No Git.
