# R2B.1 control-only routes

Baseline inspected: main 866a332d98e19a59c8a273121bde68199eb940ab.
Adds tools/lcd_stream_control_api.py and tests/test_control_api.py only, plus this checkpoint.
Reuses lcd_stream_server.make_handler Host checks, response headers, capability comparison,
socket timeout and Server; does not instantiate App, LCDStream, Session or SeekApp.
Existing legacy M4 entry points are unchanged. This is a separate explicit control-only
entry point, NOT the simulated handset dispatcher, and NOT fenced Start admission support.
The open response identifies the control wire protocol only; Start always refuses.

Validation performed during delivery: Python AST parsing of both new Python files.
HTTP tests are supplied but NOT executed in the delivery environment (repository dependencies
are unavailable there). Do not mark the real HTTP gate passed until the following commands pass.

    python3 -m unittest discover -s tests -p 'test_start_fence.py' -v
    python3 -m unittest discover -s tests -p 'test_control_api.py' -v

Run separately from M4:

    python3 tools/lcd_stream_control_api.py --bind 127.0.0.1 --port 8102

The capability is printed to the trusted local terminal, not exposed by GET /.
Keep it private; do not publish terminal logs. Header X-Wapflix-Test or existing body-token
convention authorizes requests. Trusted LAN/Tailscale only, not public authentication.

POST /api/control/open with {} returns a bounded core handle and a 60-second lease.
POST /api/control/cancel with control_client_id/cancel_through records a watermark.
No worker exists in this mode. Unexpected injected ownership returns 503 unconfirmed and is
never released or falsely reported cleaned. There is deliberately no confirmed-cleanup path
until a real coordinator exists. Production uses the default 32-client/60-second core.

Tests cover real loopback HTTP, cancellation watermark, replayed cancellation, unknown/expired
handles, capacity reclamation, safe integer/handle/body validation, Host/Origin/capability,
Start refusal, inaccessible media routes, injected expired ownership, and concurrent registration.
Injected admission callback is a unit fixture only. No FFmpeg, browser or host acceptance claimed.

Install: extract archive at repository root, checking that these new paths do not already exist.
Rollback: stop the control-only process and remove only these three added files.
Next: run the HTTP gate, then R2B.2 coordinator tests; no adapter or handset changes yet.
