# Browser account setup and recovery

Owners can create an email/password account without SSH or a generated initial
password. Existing username/password accounts and service API keys keep working.
Email is an account identifier; this flow does not verify mailbox ownership or
send password-reset email. Recovery uses saved recovery codes.

## First owner setup

1. In Render's Environment page, copy `OMNIGENESIS_ACCOUNT_SETUP_KEY`. The deployed
   service must have this random secret set to at least 32 characters. The Blueprint
   generates it for new installations; an existing service needs it added once.
2. Open the website and expand **Account setup, recovery & password** →
   **Set up owner account**. Paste the owner key, enter your email, and choose a
   password of 14–1024 characters. Confirm it; Show passwords helps check typing.
3. Download the eight recovery codes and keep them in a password manager. The
   server stores only their hashes and cannot display the codes again.
4. Sign in with your email and chosen password. The setup key cannot create
   another account after the first successful setup, even after restart. You can
   remove it from Render after setup. Keep the data directory and database intact.

Anyone with the unconsumed setup key can create the owner account. Keep it out of
source code, screenshots, logs, and public URLs. There is no open admin registration.
Setup does not merge identities or remove existing accounts.

## Password changes and recovery

- While signed in, use **Change password** with your current password. This also
  upgrades legacy username accounts by issuing their first recovery codes.
- If locked out, use **Recover account** with your email/username, one saved
  recovery code, and a new password. No shell access is needed.
- Both operations revoke all sessions for that account and replace ALL old
  recovery codes. Download the new codes immediately and sign in again.
- Disabled accounts cannot recover themselves. Service API keys cannot use the
  account password-change endpoint. Roles are preserved during recovery.
- If you lose the password and every recovery code, an authorized operator still
  needs the offline `platform_admin.py set-password` command. There is no unauthenticated
  override. Offline password resets also invalidate existing recovery codes.

Auth operations share a limit of ten attempts per minute per direct peer. Behind
a proxy, peers may share that budget. A limit response requires waiting a minute.
Passwords use scrypt; sessions are revocable, last one hour, and remain in browser
memory. Passwords, setup keys, recovery codes, and session tokens are excluded
from audit metadata and are not stored in browser localStorage.

This improves account usability but does not add MFA, OIDC, verified-email delivery,
or resolve the other public-production gates in `PRODUCTION_READINESS.md`.
