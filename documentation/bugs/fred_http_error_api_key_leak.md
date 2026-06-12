# Bug: FRED HTTP Errors Could Expose API Keys

## Bug

When FRED returned an HTTP error, the raw `httpx.HTTPStatusError` message included the full request URL.

Because the FRED API key is sent as a query parameter, that raw exception text could expose `api_key` in:

- terminal output
- ingestion failure records
- copied debugging logs

## Cause

`FredClient.fetch_series` called `response.raise_for_status()` directly.

The ingestion script records `str(exc)` for failed ingestion runs, so raw provider exceptions were not safe enough to persist.

## Fix

`FredClient.fetch_series` now catches:

- `httpx.HTTPStatusError`
- `httpx.RequestError`

It raises a sanitized `RuntimeError` that includes only the dataset symbol and status/failure class.

## Result

FRED failures now preserve useful debugging context without exposing the API key.

The regression test verifies that neither the key value nor the `api_key` parameter name appears in the surfaced error message.
