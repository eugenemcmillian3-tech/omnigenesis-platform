# Production readiness

The current release is a single-tenant private beta. A successful Render deploy
does not complete the public-production release gates below.

## Hardening implemented

- Persistent storage uses the app-owned `/var/lib/omnigenesis/data` directory.
- HTTP POST requests reject duplicate Content-Length, Transfer-Encoding,
  non-decimal lengths, incomplete bodies, and bodies above 1 MiB.
- `/api/health` checks the account database, primary database, and a temporary
  write in the durable data directory. It returns 503 while dependencies fail
  or the service drains, and bypasses ordinary request throttling.
- SIGTERM and SIGINT stop accepting work, end SSE streams, and wait up to 15
  seconds for active requests before process exit. A completed drain saves the
  core checkpoint before closing its database and the owned identity store.
  Requests still active at the deadline may be interrupted and are logged.
- The non-root Docker user has a login shell and a private `.ssh` directory,
  as required for Render shell access. Authorized public keys are still required.
- Automated tests cover malformed HTTP framing, storage-failure readiness,
  throttle-independent probes, SIGTERM exit, and shutdown checkpoint integrity.

## Remaining release gates

| Gate | Required evidence |
| --- | --- |
| Production HTTP stack | Migrate the standard-library HTTP handler to a maintained application server/framework; validate all routes, SSE, proxy behavior, and concurrency. |
| Execution isolation | Move generated-code, compiler, and native execution into resource-limited isolated jobs. AST checks alone are not a security boundary. |
| Identity | Implement and test MFA or OIDC, account recovery, individual operator accounts, and credential rotation. Rotate any password shown in chat. |
| Disaster recovery | Automate encrypted off-service backups, define recovery targets, and restore a real snapshot into a separate staging service. Local restore tests alone do not establish disaster recovery. |
| Complete persistence | Verify every supported subsystem, including custom model registrations, across restart and redeploy. |
| Monitoring | Configure external uptime checks, authenticated metrics collection, centralized audit retention, alerts, and an incident-response owner. |
| Security validation | Complete authorization/XSS review, dependency review, browser/device integration tests, and independent security review. |
| Capacity | Run load and failure tests against the deployed service and document supported limits. Keep one instance while SQLite and process-local state remain. |
| Beta access | Configure an appropriate gateway/VPN or supported allowlist before removing maintenance mode. |

## Verification

Run `.venv/bin/python scripts/verify.py` in the project environment. The hardening
revision has 42 regression tests and 64 built-in checks. CI must run successfully
for the published revision; a local pass does not prove a hosted CI pass.

After deploying, verify the exact deploy becomes `live`, inspect its runtime logs,
and test health, login, role restrictions, logout, and SSE through HTTPS. Maintenance
mode returns 503 at the public edge, so it prevents external application testing.
Use an authorized internal shell for initial checks while access restrictions are
prepared. Do not mark the remaining gates complete without their evidence.
