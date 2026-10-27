# OMNIGENESIS-Ω Platform

This repository contains the Omnigenesis platform engine, dashboard, Python SDK, deployment configuration, model definitions, and fine-tuning assets.

## Run the platform

Start the local platform with the IDE **Run** button, or:

```bash
bash .derle/run.sh
```

The launcher creates a private `.env` if needed, installs NumPy, SciPy, and cryptography in `.venv`, migrates legacy temporary stores without overwriting durable files, bootstraps the admin account, and starts the authenticated single-tenant beta on port 8080. `python3 main.py` uses the same launcher.

Open `http://localhost:8080/`, open the private `bootstrap-admin.txt` file identified by the launcher, and sign in with its username and password. Change the initial password with `.venv/bin/python platform_admin.py set-password admin`. Session tokens stay in page memory. Advanced service-key access remains available. The convergence controls, model API playground, model creation, and verification table use server responses. Connect also loads the server's route catalog into the API playground, including metrics and SSE. Network failures return errors instead of simulated successes. Some older specialist panels still contain local demonstrations; their output is not evidence of a live external integration.

For a direct launch after setup:

```bash
set -a
. ./.env
set +a
.venv/bin/python omnigenesis_engine.py --serve --port 8080
```

## Verify

Native kernel checks require GCC (or Clang), C headers, and Node.js on `PATH`. In this Ubuntu environment, install them with `apt-get install gcc libc6-dev nodejs` or the corresponding Derle Components.

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/verify.py
```

The built-in suite runs 64 local checks. Additional HTTP regression tests cover authentication, malformed inputs, convergence, model inference, Prometheus metrics, continuous SSE, and route registration. Native build artifacts are stored under `build/`. These tests verify local behavior; they do not validate scientific claims, live model inference, cloud capacity, or payment integrations.

## Optional Python SDK

Install the package and its declared SDK dependencies with:

```bash
python3 -m pip install .
```

This installs the `omnigenesis` CLI and the SDK dependencies declared in `pyproject.toml`. The server’s `cryptography` dependency is installed separately from `requirements.txt`; NumPy and SciPy are also required by scientific/server workflows.

## Optional model training

The Hugging Face training scripts require PyTorch, Transformers, Datasets, PEFT, TRL, Accelerate, and bitsandbytes. Follow the training script’s documented command and the library installation guidance for your hardware; 4-bit training generally requires a compatible GPU. Training also downloads large model weights and may require substantial storage.

## Private-beta foundations and remaining production gates

Individual accounts use scrypt password hashes and one-hour revocable sessions. The IDE Run launcher and container entrypoint enable single-tenant beta mode, blocking SaaS multi-tenant routes. Admin, operator, and reader roles retain their route restrictions. Bootstrap credentials and random per-tag signing keys are stored privately under `OMNIGENESIS_DATA_DIR` (default `~/.local/share/omnigenesis`). Databases, deployment bundles, audit logs, and core checkpoints also use that directory. Core mission, telemetry, and operators restore across restarts; some other state still needs complete recovery support.

Requests have input/body limits, login throttling, a general request limit, and a cap on concurrent connections. JSON API audit events exclude bodies and credentials. Docker excludes local secrets, runs without root privileges, and Compose adds health checks and resource limits. A TLS Nginx template and account/backup administration commands are provided. See [the private-beta runbook](deploy/PRIVATE_BETA.md) for setup, recovery, key rotation, verification, and limitations.

**This remains a private beta, not a public-production release.** The standard-library HTTP server still needs migration to a maintained production application server/framework. OIDC/MFA, full tenant isolation, background job isolation, comprehensive XSS/authorization review, complete state recovery, load/device testing, centralized monitoring, and independent security review remain launch gates. Payment processing, identity-provider JWT issuance, and remote terminal execution are disabled. Several specialist panels still contain local demonstrations; passing the development suite does not validate their external integrations or scientific claims.

## Managed hosting

A Render staging blueprint is provided in `render.yaml`. It uses a paid Docker service and persistent disk, generates service secrets, and starts in maintenance mode. See [the Render setup guide](deploy/RENDER.md). Creating a paid provider service and enabling user traffic are separate steps.
