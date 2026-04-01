VENV_PYTHON ?= .venv/bin/python

.PHONY: setup init seed run test test-e2e validate docker-build docker-up docker-down docker-smoke docker-scan

setup:
	./scripts/ubuntu_bootstrap.sh

init:
	$(VENV_PYTHON) -m aws_local_audit.cli init-db
	$(VENV_PYTHON) -m aws_local_audit.cli security bootstrap

seed:
	$(VENV_PYTHON) -m aws_local_audit.cli framework seed

run:
	./scripts/run_workspace.sh

test:
	$(VENV_PYTHON) -m unittest discover -s testing/tests -p "test_*.py"

test-e2e:
	./scripts/run_e2e_tests.sh

validate:
	./scripts/ubuntu_validate.sh

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-smoke:
	./scripts/docker_smoke.sh

docker-scan:
	./scripts/docker_scan.sh
