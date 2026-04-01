# my_grc QA Harness

This folder contains the isolated QA application for `my_grc`.

## What it covers

- static security scanning of Python source
- database bootstrap, schema, and migration smoke
- unit and regression discovery from `testing/tests/`
- offline CLI smoke against an isolated SQLite database
- Streamlit workspace startup and health smoke

## Isolation model

The harness does not touch the normal application database, logs, or secrets.

Each run creates a temporary isolated runtime with:

- a temporary SQLite database
- temporary logs
- temporary secret-files storage
- a temporary home directory
- offline mode enabled
- explicit environment overrides so `.env` is not reused by accident

Unless `--keep-run-dir` is passed, the runtime directory is deleted automatically after the run.

## Ubuntu prerequisite

If Ubuntu WSL does not yet provide `python3 -m venv`, run this yourself inside `Ubuntu-24.04`:

```bash
cd /mnt/c/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc
sudo apt-get update && sudo apt-get install -y python3.13-venv
```

## Full run

```bash
cd /mnt/c/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc
./scripts/run_e2e_tests.sh
```

Direct harness invocation is also available:

```bash
cd /mnt/c/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc
bash testing/qa/run_wsl.sh
```

## Targeted runs

Run only the static security layer:

```bash
cd /mnt/c/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc
python3 -m testing.qa.run --check security --python python3
```

Run only unit and CLI layers while keeping the isolated runtime directory:

```bash
cd /mnt/c/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc
bash testing/qa/run_wsl.sh --check unit --check cli --keep-run-dir
```

## Reports

By default the harness writes:

- `testing/qa/reports/latest.json`
- `testing/qa/reports/latest.md`
