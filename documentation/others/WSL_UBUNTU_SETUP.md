# Ubuntu WSL Setup

This is the recommended runtime path for `my_grc` today.

## System packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential libffi-dev libssl-dev sqlite3 libsqlite3-dev curl unzip ca-certificates
```

Install AWS CLI v2:

```bash
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

Optional browser evidence support for screenshots:

```bash
sudo apt install -y chromium-browser chromium-chromedriver
```

If your Ubuntu release uses different package names, install the equivalent Chromium and ChromeDriver packages for that distribution.

## Project setup

```bash
cd /path/to/my_grc
./scripts/ubuntu_bootstrap.sh
```

Manual setup if you prefer not to use the bootstrap script:

```bash
cd /path/to/my_grc
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Optional Selenium support:

```bash
pip install -e .[browser-evidence]
```

## Initialize the app

```bash
cp .env.example .env
mkdir -p data/secrets
aws-local-audit init-db
aws-local-audit security bootstrap
aws-local-audit framework seed
```

## Run the workspace

```bash
./scripts/run_workspace.sh
```

## AWS CLI SSO profile workflow

The recommended behavior is:

1. register AWS CLI profile metadata in the app
2. bind frameworks and define AWS evidence targets
3. inspect the required login plan before a collection or assessment run
4. run `aws sso login --profile <profile>` for each required profile
5. return to the app and continue with evidence collection

Useful commands:

```bash
aws-local-audit aws-profile upsert my-sso-profile \
  --sso-start-url https://example.awsapps.com/start \
  --sso-region eu-west-1 \
  --sso-account-id 123456789012 \
  --sso-role-name AuditReadOnly \
  --default-region eu-west-1

aws-local-audit aws-profile show-config my-sso-profile
aws-local-audit aws-profile export-config
aws-local-audit aws-profile validate my-sso-profile
aws-local-audit evidence login-plan --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 --product CUSTOMER_PORTAL
aws-local-audit evidence readiness-report --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 --product CUSTOMER_PORTAL
aws-local-audit maturity phase1-score
aws-local-audit maturity enterprise-score
aws-local-audit review queue
./scripts/ubuntu_validate.sh
./scripts/docker_smoke.sh
./scripts/docker_scan.sh
aws sso login --profile my-sso-profile
```

## Offline-first mode

If you want to work locally without live AWS access:

```bash
export ALA_OFFLINE_MODE=true
export ALA_SECRET_FILES_DIR="$(pwd)/data/secrets"
./scripts/run_workspace.sh
```

In offline-first mode the workspace remains usable for frameworks, controls, mappings, questionnaires, assessments, and reporting. New evidence collection is deferred and assessments reuse existing local evidence.
