# Project Instructions

## Public Repository — No PII

This is a public repository. Never commit personal identifying information:
- No real names, email addresses, or usernames in code, docs, or examples
- No home network IPs (192.168.x.x with specific hosts) — use `10.0.0.x` for examples
- No hardcoded SSH usernames — use `$(whoami)` or `user@` in scripts/docs
- No home directory paths like `/home/<username>/` — use `$HOME`, `~/`, or generic paths like `/home/pi/`
- Default IPs in code should be generic (e.g. `10.0.0.1`) and overridable via environment variables
