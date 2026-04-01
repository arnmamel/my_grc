# Docker Plan

## Current recommendation

Use Ubuntu WSL plus a Python virtual environment as the primary interactive runtime.

Use Docker for:

- offline-first workspace hosting
- repeatable local deployment
- non-interactive or semi-interactive enterprise operation
- a future path toward controlled server deployment

## Container direction

The project is now prepared for an Alpine-based container runtime.

### Supported container posture

- offline-first mode by default
- local metadata, reporting, and workspace browsing inside the container
- optional mounted persistent volume for SQLite data
- optional mounted `~/.aws` configuration from the host when evidence collection is needed
- secret storage through a private secret-files directory rather than environment variable values

### Important limitation

Interactive `aws sso login` should remain host-driven. The container should reuse host-managed AWS CLI configuration and cached SSO sessions only when that mode is explicitly chosen.

## Runtime image strategy

Implemented:

- multi-stage build
- Alpine 3.23 based Python image
- migration-aware container startup
- non-root runtime user
- `tini` entrypoint
- healthcheck against Streamlit
- compose-based local deployment
- persistent `data/` volume
- smoke-test and scan scripts for promotion checks

Reference baseline used for this plan:

- Alpine Linux 3.23.x is the latest stable release family listed by Alpine at the time of writing
- official Python image tags include Alpine 3.23 variants in the current stable Python line; this project is prepared around `python:3.14.3-alpine3.23`

## What the included Docker assets are for

The included `Dockerfile`, `compose.yaml`, `.streamlit/config.toml`, and `scripts/docker-entrypoint.sh` support:

- offline-first workspace use
- local metadata administration
- non-interactive service execution
- repeatable Ubuntu-hosted container runs

Interactive `aws sso login` should still happen on the host. The container should reuse host-managed AWS CLI configuration and cached SSO sessions only when that mode is intentionally enabled.

## Security posture

- do not inject Confluence or encryption secrets through environment variables
- use the `ALA_SECRET_FILES_DIR` path inside the persistent data volume for container-friendly secure storage
- prefer mounted host AWS configuration over storing AWS credentials in the container
- run the container as a non-root user

## Vulnerability posture

The Docker assets are prepared to support a low-vulnerability baseline, but zero-vulnerability status cannot be guaranteed statically in source control. It depends on:

- the exact image digest resolved at build time
- the current package indexes
- the dependency graph produced in the build environment

For that reason, the operational requirement should be:

1. build from the current Alpine image tag
2. scan the built image in CI or on the target Ubuntu machine
3. only promote the image if the scan is clean for the accepted severity policy

Recommended scanners:

- `docker scout`
- `trivy`
- `grype`

Included helper scripts:

- `./scripts/docker_smoke.sh`
- `./scripts/docker_scan.sh`

## Example commands

Build:

```bash
docker compose build
```

Run in offline-first mode:

```bash
docker compose up -d
```

Run with host AWS configuration mounted for controlled evidence collection:

```bash
docker run --rm -p 8501:8501 \
  -v "$(pwd)/data:/app/data" \
  -v "$HOME/.aws:/app/.aws:ro" \
  -e ALA_OFFLINE_MODE=false \
  -e ALA_SECRET_FILES_DIR=/app/data/secrets \
  -e AWS_CONFIG_FILE=/app/.aws/config \
  -e AWS_SHARED_CREDENTIALS_FILE=/app/.aws/credentials \
  my-grc:alpine
```

For now, use this mode only when the host has already completed the required `aws sso login` operations.
