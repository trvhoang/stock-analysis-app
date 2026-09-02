# Flexible Rulebook UI Scope Expansion and Progress — Verification

## Result

Complete. Discover can expand the active ticker/seed scope through one
operator-confirmed action. The request freezes the additive union and the
latest common completed bar returned by a fresh full-union preflight. A
durable benchmark job runs outside the evidence root and activates a new
policy only after every union pair has 100 eligible cold windows. Existing
policy authority is unchanged during queued, running, failed, or cancelled
states.

When eligible members have different latest bars, the request uses the
minimum per-ticker latest completed bar—the latest bar available to the full
union.

Qualification and Current Group BUY Scan now expose phase-aware progress
callbacks and Streamlit progress bars. Discover campaign progress is derived
from its persisted frontier cursor; expansion progress is read from its
canonical status sidecar after refresh.

## Verification

```text
docker compose --env-file .env -f docker/docker-compose.yml exec -T app \
  python -m unittest discover -s tests -p "test_flexible_rulebook*.py"
321 tests passed

docker exec stock_app python -m py_compile \
  pages/flexible_rulebook.py flexible_rulebook/service.py flexible_rulebook/current_scan.py
passed

docker exec stock_app python -m unittest \
  tests.test_flexible_rulebook_page \
  tests.test_flexible_rulebook_service \
  tests.test_flexible_rulebook_current_scan
passed
```

### Metadata-default amendment (2026-08-31)

The scope expander now initializes editable operator identity to `admin
DDMonYY` using the Ho Chi Minh date and builds its editable approval note from
the normalized added tickers. A ticker change refreshes only that generated
note; manually entered approval wording remains untouched. A pre-existing
browser session with the old blank metadata receives the defaults once.
Three AppTest regressions cover generated metadata, manual-note preservation,
and the old blank-session repair. The full Flexible Docker gate above passes
321 tests, and `py_compile pages/flexible_rulebook.py
tests/test_flexible_rulebook_page.py` passes.

### Live-progress polling repair (2026-08-31)

The expansion worker already wrote every window update atomically to its
sidecar, but Streamlit rendered that value only once unless the operator
pressed `Refresh Scope Expansion`. Queued/running scope jobs now wait three
seconds and rerun through the existing injected refresh boundary; terminal
states do not poll and retain manual refresh for `interrupted`. One AppTest
proves an active durable sidecar causes a refresh, while the existing terminal
failure test proves no active-poll path is needed there. The full Flexible
Docker suite passes 321 tests.

The Streamlit runtime emitted third-party `SyntaxWarning` messages only; the
test process exited successfully. The activation CLI module-reexecution
warning regression is covered and passes after lazy-loading the coordinator.

## Safety review

- Scope input is normalized, deduplicated, and rejected when additions are
  duplicate-only, invalid, or missing operator metadata.
- Common-as-of is not typed or guessed; it is recomputed for the complete
  union immediately before request creation.
- Progress callbacks swallow telemetry failures and cannot alter evidence,
  qualification, scan results, or activation eligibility.
- No SQL path, price scaling, timezone contract, V3, positions, Docker,
  dependency, or git state was changed.
