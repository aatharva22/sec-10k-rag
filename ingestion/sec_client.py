"""
Shared EDGAR HTTP client.

Responsible for:
- attaching the SEC-required `User-Agent` (read from env: SEC_USER_AGENT)
- enforcing a polite request rate (<= 10 req/s per SEC fair-access policy)
- returning raw bytes/text for callers to parse

Used by Phase 1 download subagents and any later code that needs to reach EDGAR.

TODO Phase 1:
- expose `get_json(url) -> dict` and `get_bytes(url) -> bytes`
- token-bucket or simple sleep-based rate limit (100ms min spacing per process)
- raise a clear error if SEC_USER_AGENT is unset
"""
