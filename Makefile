# Knight School. `make help` lists targets.
UV ?= $(HOME)/.local/bin/uv
KS := $(UV) run ks

.PHONY: help setup lint test costs reconcile sweep prices data upload-data eval image

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

SET ?= dev500
eval: ## run the eval harness: MODEL=<profile> SET=dev500|test2000|test500|chessbench1k|probe500 [CKPT=gs://...] [ARGS=...]
	$(KS) eval $(MODEL) --set $(SET) $(if $(CKPT),--ckpt $(CKPT),) $(ARGS)

PROJECT = $(shell grep -E '^GOOGLE_CLOUD_PROJECT=' .env | cut -d= -f2 | cut -d' ' -f1)
GIT_SHA = $(shell git rev-parse --short=12 HEAD)
IMAGE = us-central1-docker.pkg.dev/$(PROJECT)/knight-school/train

image: ## build and push train:<git-sha> with Cloud Build (billable: ask first; clean tree only)
	@test -z "$$(git status --porcelain -- ks configs docker evals pyproject.toml)" || { echo "commit first: the tag is the git sha"; exit 1; }
	$(GCLOUD) builds submit --project $(PROJECT) --region us-central1 --config docker/cloudbuild.yaml \
		--substitutions _IMAGE=$(IMAGE),_GIT_SHA=$(GIT_SHA) .
