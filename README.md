# OMNIGENESIS-Ω Platform

An experimental Python platform with a browser dashboard, HTTP API, server-sent events (SSE), Prometheus metrics, Python SDK, Ollama model definitions, and Hugging Face fine-tuning assets.

The project explores runtime operator generation, convergence workflows, and multi-agent simulations. Names such as AGI, ASI, and “5th paradigm” describe the project's concepts; they are not evidence of demonstrated general or superhuman intelligence.

## Current development status

The published repository is an experimental development snapshot. Local follow-up work includes authenticated single-tenant beta access, account administration, durable storage, regression tests, and managed staging configuration. Those changes are pending publication and are not included merely by updating this README.

The instructions below use files currently available in this repository. Private-beta setup instructions will accompany the corresponding code.

## Local quick start

Use Python 3.10 or newer. From a terminal:

```bash
git clone https://github.com/eugenemcmillian3-tech/omnigenesis-platform.git
cd omnigenesis-platform
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install .
python3 omnigenesis_engine.py --serve --port 8080
```

Open http://localhost:8080/ in your browser. Keep this development server on a trusted local environment.

For a command-line engine run:

```bash
python3 omnigenesis_engine.py --goal "Explore a convergence workflow" --cycles 4
```

In the Derle workspace, the IDE Run button reads `.derle/run.sh`. That workspace launcher belongs to the local development setup and is not currently included in the published repository.

## Verification

With the virtual environment activated:

```bash
python3 omnigenesis_engine.py --self-test
```

Native compilation checks require GCC or Clang with C headers, and JavaScript checks require Node.js. On Ubuntu, install these prerequisites with:

```bash
sudo apt-get update
sudo apt-get install gcc libc6-dev nodejs
```

In Derle's proot Ubuntu environment, omit `sudo` or install the corresponding tools through Components / SDKs.

Inspect the actual self-test report for the check count and failures. Local checks do not establish scientific validity, model quality, production capacity, or working external integrations.

## Repository guide

| Path | Purpose |
| --- | --- |
| [omnigenesis_engine.py](omnigenesis_engine.py) | Engine, HTTP API, SSE, metrics, and built-in checks |
| [omnigenesis_dashboard.html](omnigenesis_dashboard.html) | Browser command deck served by the engine |
| [omnigenesis_sdk/](omnigenesis_sdk/) | Python client and CLI |
| [pyproject.toml](pyproject.toml) | Package metadata and Python dependencies |
| [ollama_models/](ollama_models/) | Ollama Modelfiles and model build script |
| [huggingface_finetune/](huggingface_finetune/) | Training scripts, example data, and export tooling |
| [deploy/](deploy/) | Existing deployment examples |
| [Dockerfile](Dockerfile) / [docker-compose.yml](docker-compose.yml) | Container configuration |

## Python SDK and CLI

`python3 -m pip install .` installs the SDK, its declared dependencies (NumPy, SciPy, and cryptography), and the `omnigenesis` command.

Review [the client implementation](omnigenesis_sdk/client.py) and [CLI](omnigenesis_sdk/cli.py) for supported operations.

## Optional model workflows

The Ollama definitions require a separate Ollama installation and the base models named in each Modelfile. Review [the build script](ollama_models/build_omni_ollama_models.sh) before running it.

The Hugging Face scripts use additional libraries such as PyTorch, Transformers, Datasets, PEFT, TRL, Accelerate, and bitsandbytes. These training dependencies are separate from the SDK installation. Review each script's arguments and hardware requirements before downloading model weights or starting training.

Model definitions and example training data do not establish that a trained model or hosted inference service is available.

## Deployment status and remaining work

The existing container and host deployment files are development examples that need review before use. The published Dockerfile includes a placeholder payment webhook secret; it must not be treated as a production credential. Installing the SDK locally does not install dependencies inside the existing container image.

Before accepting public traffic, complete authentication and authorization review, secret management, TLS, durable storage and recovery, job isolation, production application-server migration, monitoring, load testing, and an independent security review. Verify external integrations individually. Some dashboard outputs are demonstrations or local calculations.

The next publication should include the private-beta code, tests, and deployment runbooks together so documented commands and available files stay aligned.
