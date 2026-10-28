# Managed staging on Render

The root `render.yaml` prepares one paid Docker web service with a 1 GB persistent disk,
private-beta mode, generated service secrets, health checks, and manual deploys.
It starts in maintenance mode so an unvalidated staging instance does not accept users.
No provider resources are created by adding these files.

## Create staging

1. Push this repository to a private GitHub or GitLab repository accessible to your Render account.
2. In Render, create a Blueprint from that repository. Review the service plan, region,
   persistent-disk charges, and generated configuration before confirming creation.
   The blueprint selects `standard`; inspect current pricing before accepting it.
3. Render builds the Dockerfile and runs `deploy/start-beta.sh`. The service binds to
   `0.0.0.0` and uses Render's injected `PORT`. Do not hard-code port 8080 in the dashboard.
4. Confirm deployment/health checks pass. In the service shell, verify that the configured
   non-root service user can write to `/var/lib/omnigenesis`. If disk permissions prevent
   startup, correct ownership for the service user through the host/provider configuration;
   retain the non-root runtime.
5. Retrieve `/var/lib/omnigenesis/bootstrap-admin.txt` using Render's service shell.
   Change the initial password with `python3 platform_admin.py set-password admin`.
   Keep credentials out of screenshots, issue trackers, and build logs.
6. Before disabling maintenance mode, complete the private-beta access restriction and
   application-server review described below. When ready, change `maintenanceMode.enabled`
   to `false` and sync the Blueprint. Render assigns an HTTPS `onrender.com` address;
   a custom domain can be added later.

## Validation before inviting testers

- Confirm the public health endpoint, login, role restrictions, logout, and SSE work
  through the provider's HTTPS proxy. The local Nginx example is not deployed on Render.
- Create a test mission, restart/redeploy the service, and confirm its checkpoint and
  signing key persist. All durable state must remain under the disk mount path.
- Test backup restoration into a separate staging environment. Download an encrypted
  off-service backup; a backup stored only on the same disk is not disaster recovery.
- Keep a single instance. This version uses SQLite and process-local state; it is not
  configured for replicas or horizontal autoscaling. Disk-backed deploys can interrupt service.
- Inspect host logs and resource use. The application still uses Python's standard-library
  HTTP backend, so application-server migration, job isolation, MFA, and a security review
  remain release gates. Maintenance mode is not a replacement for those changes.
- Restrict beta access with an appropriate gateway/VPN or Render access controls available
  on your workspace plan. Do not assume IP filtering is included in the selected compute plan.

This creates a new cloud installation; it does not upload your phone's accounts, signing
keys, or databases. Any later data migration needs a separately reviewed backup/restore step.
Automatic deployments are disabled so updates and database compatibility can be reviewed.

References: [Docker](https://render.com/docs/docker),
[persistent disks](https://render.com/docs/disks),
[Blueprint fields](https://render.com/docs/blueprint-spec),
[current pricing](https://render.com/pricing).
