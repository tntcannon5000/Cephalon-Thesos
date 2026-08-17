# Phase 3B Private Alpha

## Access model

Thesos is closed by default. Registration succeeds only for an exact normalized address in
`access_allowlist`; it collects an email address and password, then requires email verification.
Authentication uses opaque server-side sessions in Secure, HttpOnly cookies and a separate CSRF
cookie/header pair. Passwords use Argon2id. Session, device, email-action, and recovery values are
stored only as keyed digests.

The bootstrap command is intentionally idempotent and keeps tester addresses out of tracked files:

```sh
uv run --project apps/api python -m veris_api.manage bootstrap-access \
  --email admin@example.com \
  --admin-email admin@example.com \
  --email tester@example.com
```

Run it after `alembic upgrade head`. `--admin-email` may initialize only the first administrator.
Subsequent allowlist and role changes belong in the audited admin interface.

Local email delivery writes ignored HTML messages under `var/dev-mail`. Production requires Resend,
a verified sending identity, and `PUBLIC_BASE_URL=https://chat.cephalonthesos.com`. Verification and
reset secrets are placed in URL fragments so reverse-proxy access logs do not receive them.

## Administrator enrollment

The first administrator logs in normally, opens `/admin`, and enrolls TOTP. Save the one-time
recovery codes outside the VM before confirming enrollment. Admin API access is unavailable until
enrollment is confirmed; afterwards every new admin login requires TOTP or one unused recovery
code. Admin sessions have shorter idle and absolute lifetimes than tester sessions.

## Usage enforcement

Each accepted run reserves one unit atomically against four limits:

- the account's UTC-day allowance, 10 by default;
- the first-party random device cookie, 10 by default;
- a rotating-key HMAC pseudonym of the trusted client IP, 10 by default;
- the service-wide UTC-day budget, 100 by default.

The reservation is charged when provider work begins. A dispatch failure or cancellation before
that point releases it; provider-started work remains charged. Idempotent retries reuse the original
run and unit. Per-account concurrent work is capped separately. Operators may approve a dated,
one-off grant or set an account-specific baseline from the admin interface.

Thesos does not use canvas, font, audio, GPU, or other invasive browser fingerprinting. The API is
not exposed directly in production, and only the configured Caddy network is trusted to supply
forwarding headers.

## Persistence and retention

Authenticated conversations and preferences are authoritative in PostgreSQL and cached per account
in the browser. Existing local prototype conversations migrate once into the first authenticated
account only when that account has no server history. Cross-account access is checked server-side
for reads, writes, branches, edits, streams, and cancellation.

Run prompt/answer content is scrubbed from operational records after 24 hours; terminal run records
and events expire after `RUN_RETENTION_DAYS`. Security records and content-free audit history use
their own bounded retention windows. Daily aggregate counters are retained for 90 days.

## Production checklist

1. Generate three independent random secrets for sessions, IP pseudonyms, and MFA encryption.
2. Configure the PostgreSQL URLs, Resend identity/key, Turnstile site/secret keys, and trusted proxy CIDRs.
3. Apply migrations and run the out-of-band access bootstrap.
4. Register and verify the initial admin, enroll MFA, and secure the recovery codes.
5. Exercise registration, verification, login, reset, suspension, quota exhaustion, and one grant.
6. Confirm ordinary users receive `404` from admin routes and cannot access another account's IDs.
7. Inspect content-free usage/cost metrics, audit events, retention logs, and backup health daily during the private alpha.
