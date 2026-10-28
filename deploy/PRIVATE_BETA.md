# Private single-tenant beta

This is a restricted local/private-beta configuration, not approval for a public launch.
All accounts share one trusted organization's workspace. Multi-tenant SaaS routes are
blocked when `OMNIGENESIS_PRIVATE_BETA=1`; do not disable this flag for customer use.

## Local startup and login

For browser-based email/password setup and recovery without SSH, see
[Browser account setup](BROWSER_AUTH.md). Existing username accounts remain valid.

Run `bash .derle/run.sh` (or the IDE Run button). It installs the Python dependencies,
non-destructively copies legacy databases from `/tmp` when no durable copy exists,
and creates the initial admin account only if the account database is empty.
The command prints the location of `bootstrap-admin.txt`, not the password itself.
Open that file locally, sign in using the dashboard's username/password fields,
and change the initial password:

```bash
.venv/bin/python platform_admin.py set-password admin
```

This command prompts without echoing the password and removes the bootstrap file.
Passwords must contain at least 14 characters. Login sessions expire after one hour;
sign-out, password changes, and account disabling revoke sessions. Session tokens stay
in page memory and are sent as bearer credentials. Reloading the page requires login.
There is no public registration, password-reset email, OIDC provider, or MFA yet.
Saved recovery codes support browser password recovery; signed-in accounts can
change their passwords and generate replacement codes in the account panel.
Service API keys remain available for SDKs and offline administration; guard them as secrets.

Create individual accounts and assign only the permissions needed:

```bash
.venv/bin/python platform_admin.py create-user alice --role reader
.venv/bin/python platform_admin.py create-user bob --role operator
.venv/bin/python platform_admin.py disable-user alice
```

Admin users can access sensitive state and execution endpoints. Reader/operator
accounts deliberately cannot use all admin-oriented dashboard features.

## Durable storage and signing keys

`OMNIGENESIS_DATA_DIR` controls account/session storage, module databases, the core
checkpoint, deployment bundles, signing keys, and audit logs. The default is
`~/.local/share/omnigenesis`; Compose mounts `/var/lib/omnigenesis` as a persistent volume.
Use the same setting for the server and every administration command.

The migration copies SQLite databases using SQLite's backup API and leaves legacy
files untouched. Existing destination files always win. The core restores its saved
goal, telemetry, weights, and AST-revalidated operators. Some other subsystem state,
including custom model registrations, still needs full restart-recovery coverage.

Signing keys are random 32-byte private keys, independently stored per logical tag.
They are no longer derived from source-code strings. Key files and account databases
are private to the service user. Keep the whole data directory and backups private.
Historical receipts created with the old predictable keys must not be trusted as
proof of authenticity. For an intentional key rotation:

```bash
.venv/bin/python platform_admin.py rotate-signing-key SIGNER_TAG
```

Stop the service before rotation, then restart every application process. The previous
public key is archived; the previous private key is replaced. A verification policy
and trust/revocation registry for distributed consumers are still required.

## Backup and restore drill

Stop the application first for a consistent snapshot across separate module databases.
The backup command creates a new destination, takes a transactional snapshot of each
SQLite database, checks its integrity, and copies the remaining data, including keys:

```bash
.venv/bin/python platform_admin.py backup /path/to/private/backups/beta-001
```

The destination must not already exist or be inside the data directory. Backups contain
sensitive data and are not encrypted by this command. Store an encrypted off-device
copy and test restoration periodically. To restore, stop the service, retain its current
data directory as a rollback copy, and copy the backup into a fresh private directory.
Set `OMNIGENESIS_DATA_DIR` to that directory. Clear the restored `sessions` table in
`identities.sqlite3` before restarting so old sessions are not resurrected. Run SQLite
integrity checks, verify account login, confirm the saved mission and operators, and
check receipt verification before accepting traffic. Never restore over a running DB.

## Restricted host deployment

The container now uses a verified Python 3.13 dependency lock, runs as a non-root user,
boots through `deploy/start-beta.sh`, and keeps secrets out of the Docker build context.
Compose adds restart/health checks, process/memory/CPU limits, and drops Linux capabilities.
The backend port remains published on host loopback only.

Before running Compose, supply private random service keys and the JWT secret in the
host environment or a protected `.env`. Do not copy `.env` into an image or repository.
Use `docker compose exec omnigenesis-core cat /var/lib/omnigenesis/bootstrap-admin.txt`
locally to retrieve the initial password. After login, change it with
`docker compose exec omnigenesis-core python3 platform_admin.py set-password admin`.
The application bootstrap path does not provision a domain, certificate, or external account.

`deploy/nginx-beta.conf.example` is a template for a host-level Nginx gateway.
Replace its domain and certificate paths, provision certificates, restrict inbound
access to a VPN or beta allowlist, and run `nginx -t` before enabling it. Forward only
through that gateway. It redirects HTTP to HTTPS, limits requests and connections,
and disables response buffering for SSE. Nginx rate limiting follows its
[official module documentation](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).
The old `nginx-omnicloud.conf` is a local HTTP example, not the TLS configuration.

The backend currently still uses Python's standard-library HTTP server. Its requests
are bounded to 16 concurrent connections (including streams), with 240 requests/minute
and 10 login attempts/minute per direct peer. Limits are process-local and proxy traffic
shares the proxy's direct-peer limit; the gateway must also enforce client limits.
The server does not trust arbitrary forwarded-address headers. A maintained application
server/framework migration is still required before general production exposure.

## Verification, operations, and remaining gates

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/verify.py
```

The script runs regression tests and 64 built-in checks in separate disposable data
directories. The dashboard's server self-test also runs in an isolated child process.
GitHub Actions runs the same command using the locked Python 3.13 environment.
The workflow runs on pushes and pull requests when GitHub Actions is enabled. Inspect the actual workflow result before treating a revision as CI-verified.
Docker and Nginx configuration must be checked on a host where those tools are installed.

Monitor `/api/health`, authenticated `/metrics`, and private `audit.jsonl` (with one rotated
previous file). Audit events contain selected request/account metadata, not bodies,
passwords, or bearer tokens. Add centralized storage, alerts, retention policies, and an
incident-response owner before inviting users.

Remaining launch gates include OIDC/MFA and account recovery, stronger isolation of
code/compilation jobs, comprehensive XSS and authorization review, background queues,
full state recovery, real integration tests, browser/device tests, load testing,
production server migration, and independent security review. Several specialist panels
and reports still represent local demonstrations or calculations. Payment integrations,
identity-provider JWT issuance, and remote shell execution remain disabled.
