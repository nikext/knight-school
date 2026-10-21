# Knight School. `make help` lists targets.
UV ?= $(HOME)/.local/bin/uv
KS := $(UV) run ks

.PHONY: help setup lint test costs reconcile sweep prices data upload-data eval

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## uv sync and install the pre-commit hooks
	$(UV) sync
	$(UV) run pre-commit install

lint: ## ruff, ruff format --check, pyright
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run pyright

test: ## unit tests (no cloud access)
	$(UV) run pytest

costs: ## ledger totals per pool and milestone vs caps
	$(KS) costs

reconcile: ## close finished runs in the ledger with their actual cost
	$(KS) reconcile

sweep: ## list everything that can bill by the hour (DELETE=1 deletes ours)
	$(KS) sweep $(if $(filter 1,$(DELETE)),--delete,)

prices: ## fetch spot prices into costs/prices.yaml (verified: false)
	$(KS) prices

data: ## M1: puzzles -> splits -> positions -> reward tables -> primer (skips unchanged steps)
	$(KS) data

GCLOUD ?= $(HOME)/google-cloud-sdk/bin/gcloud
BUCKET = $(shell grep -E '^BUCKET=' .env | cut -d= -f2 | cut -d' ' -f1)

upload-data: ## M1: copy data/ (minus raw/, logs/, reward shards) to the bucket under data/v1/ (adds, never deletes)
	$(GCLOUD) storage rsync --recursive \
		--exclude='^(raw|logs|positions/rewards)/' data/ $(BUCKET)/data/v1/

eval: ## M2: run the eval harness (MODEL=... SET=dev)
	@echo "make eval arrives in M2 (docs/tasks/M2-evals-baselines.md)"; exit 1
