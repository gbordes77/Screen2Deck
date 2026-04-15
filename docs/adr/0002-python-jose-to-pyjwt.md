# ADR 0002 — python-jose → PyJWT migration

- **Status**: Accepted
- **Date**: 2026-04-14
- **Commits**: `a9f0e3a feat(security): migrate python-jose → PyJWT, fix IDOR bypass`

## Context

Screen2Deck's authentication layer signed and verified JWTs with
`python-jose==3.3.0`, chosen originally for its nice `jwt.encode/decode`
API and support for multiple algorithms.

In 2024 two CVEs landed against python-jose:

- **CVE-2024-33663** — algorithm confusion in `jwt.decode()`. An attacker
  could craft a token that the library accepted with the wrong algorithm
  family (HS256 verified against an RSA public key, effectively bypassing
  signature verification).
- **CVE-2024-33664** — JWT decompression bomb. A malicious token with a
  compressed payload (`zip` header) could be expanded to an arbitrary size
  and exhaust server memory.

The upstream `python-jose` project was no longer receiving active security
maintenance (last real release 2022), and both CVEs were unpatched as of
our audit date.

Separately, the `AuthMiddleware` at `backend/app/core/auth_middleware.py`
had two short-circuit paths (`RATE_LIMITED_PUBLIC` and `/api/export/*`)
that set `request.state.token_data = None` unconditionally. This made the
IDOR ownership check on `GET /api/ocr/status/{job_id}` — which relied on
`token_data.user_id == job.user_id` — silently dead code: it only fired
when `token_data` was set, which was never the case for unauthenticated
paths, meaning any anonymous user could read any job they knew the
job_id of.

## Decision

Migrate every JWT consumer to PyJWT ≥2.8 (upgraded to ≥2.12.1 in
`655bbab`). Require the `exp` claim explicitly on every decode call via
`options={"require": ["exp"]}` (confirmed canonical via Context7 docs).
Replace the short-circuit `AuthMiddleware` with an optional-auth
middleware: it always populates `request.state.token_data`, never
short-circuits, and never returns 401 from the middleware itself.
Individual endpoints enforce authentication with `Depends(get_optional_token)`
and apply the ownership check unconditionally when `job.user_id` is set.

Files touched:

- `backend/app/auth.py` — PyJWT import + `options={"require": ["exp"]}`
- `backend/app/core/auth_middleware.py` — optional-auth rewrite
- `backend/app/routers/auth_router.py` — PyJWT import
- `backend/app/api/websocket.py` — PyJWT import
- `backend/requirements.txt` — drop `python-jose`, add `PyJWT>=2.8`
  (later `>=2.12.1,<3`)

## Consequences

### Positive

- Both CVEs closed. `safety check` on the backend requirements no longer
  reports either CVE-2024-33663 or CVE-2024-33664.
- IDOR vulnerability on `/api/ocr/status/{job_id}` fixed. The ownership
  check now runs on every request regardless of auth state.
- Fewer moving parts: PyJWT has a smaller API surface than python-jose
  and no cryptography plugin layer.
- PyJWT is actively maintained (versions landing every ~2 months as of
  2026-04) so future CVEs get patched.

### Negative

- PyJWT doesn't support the nested JWE / JOSE features that python-jose
  had. We never used them, so this is a paper loss, but any future
  contributor who needs them will have to pick a different lib.
- The `options={"require": [...]}` API is different from the old
  `require_exp=True` kwarg. Contributors familiar with the old API have
  to learn the new form.
- The new `AuthMiddleware` is ~80 lines longer than the original because
  it has to populate `token_data` for every code path (including the
  previously short-circuited ones) and still emit rate-limit headers.

## Related

- Commit `a9f0e3a` (PR #2 original landing of the migration)
- Commit `655bbab` (dependency sweep bumping PyJWT to 2.12.1)
- CVE-2024-33663 — https://www.cve.org/CVERecord?id=CVE-2024-33663
- CVE-2024-33664 — https://www.cve.org/CVERecord?id=CVE-2024-33664
