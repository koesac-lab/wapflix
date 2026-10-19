# LAN access for milestone 2

This small installer modifies only tools/lcd_stream_server.py from the original M2 archive. It refuses mismatched revisions, compiles the result before writing, creates an exclusive .before-lan.bak backup, and replaces the server file atomically. Re-running it is harmless after a successful installation. It does not alter Pages, the handset UI, the chunker or media.

Stop the running server with Ctrl-C. Extract this archive in the repo root, then run:

python3 tools/enable_m2_lan.py
python3 tools/lcd_stream_server.py --bind 0.0.0.0 --port 8101

Open http://YOUR_MINI_PC_LAN_IP:8101/ from another device. Use hostname -I on the mini PC to list its addresses, or tailscale ip -4 for its Tailscale IPv4 address. 0.0.0.0 is a listening address, not the address to type in the browser.

Direct LAN/Tailscale IPv4 access on the same numbered port works without hostname aliases. If you want a local hostname, add --allow-host mini-pc.local (replace with your real hostname). Existing same-origin and session-token checks remain; Host validation now accepts the actual local destination IP of each incoming connection. Arbitrary Host headers are not accepted by default. --bind still defaults to 127.0.0.1 unless explicitly changed.

This is trusted-network development access, not public internet authentication. Anyone who can open the page can obtain its session token and control the single session. Do not port-forward the service publicly or expose it through a public tunnel. Firewall and Tailscale rules still apply. Reverse proxies/HTTPS frontends are not configured by this patch.

Validation: nine Host cases, wildcard-listening HTTP smoke checks over loopback, idempotent installer, refusal on mismatched source, backup preservation. LAN/Tailscale addresses were simulated for Host validation; real-device reachability and the full streaming suite still need local verification.
