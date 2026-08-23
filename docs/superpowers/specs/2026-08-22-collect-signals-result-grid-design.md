# Collect Signals Result Grid Design

**Date:** 2026-08-22
**Status:** Implemented and verified

## Behavior

After a Collect Signals run, render output artifacts in stable status-output
order as a four-column grid. Each item keeps its existing caption, terminal
state message, and JSON download. The fifth item begins a new row.

## Boundaries

This is presentation only. It does not alter job status polling, artifact
loading, persistence, signal data, SQL, raw-BIGINT scaling, dependencies, or
Docker configuration.
