# Backtest Group Management and Append-Only Ingestion Verification

Date: 2026-08-14

## Result

The implementation is complete and verified in the running `stock_app`
container. No commit was created.

## Verified behavior

- Current signal artifacts now use `app/backtest-result/ticker-signals`; Group
  membership uses UUID-backed JSON files in `app/backtest-result/ticker-group`.
- The four approved V2 artifacts migrated byte-for-byte. Legacy source files
  are absent; 70 historical `app/backtest-status` JSON files have unchanged
  SHA-256 hashes.

| Ticker | SHA-256 |
| --- | --- |
| BID | `429ac7fcd1e1a50b00e8641e9d8a6767792f0cf050e2d5dcd42fb496ce455919` |
| TCX | `87005eef2c8419e152648e8382ae087aabc2f37098d829685325cb7610e4e39b` |
| VCB | `542c4cbccb080e658f9d7bf97e32edf9086c8536f4d074939d94fbb75db8ca5a` |
| VCI | `a43ffc132739243856354ab389c98ed04c021528b1ff103a4e461ba986c13113` |

- Collect stores uppercase Group text with each qualified ticker’s final batch
  output. Empty final output preserves its prior Group; Group-store failures are
  isolated and retried per ticker.
- Both View Signals popovers filter by ticker and Group without exposing UUIDs.
- Validate Signals supports manual one-to-five tickers or a locked Group/N/A
  list up to fifteen, skips absent/empty/unreadable artifacts, and validates
  eligible tickers sequentially.
- Data ingestion downloads Stock and VN-Index sources before opening a DB
  connection, then stages and commits all append-eligible rows in one raw
  connection transaction. Existing rows are not replaced; any stage failure
  rolls back every new row. BIGINT price `* 1000` conversion is unchanged.

## Evidence

```text
docker exec stock_app python -m unittest ...
Ran 96 tests in 4.752s
OK

docker exec stock_app python -m compileall backtest_engine pages
Compiled all changed Backtest and Data Page modules.

GET http://127.0.0.1:3501 from stock_app
200
```

`git diff --check` passed. No SQL price division, protected
`common_queries.py` change, credential change, Docker change, or production
Backtest/Get data job was performed.
