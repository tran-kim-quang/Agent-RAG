LOCAL_UID := $(shell id -u)
LOCAL_GID := $(shell id -g)
DOCKER_ENV := LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID)
COMPOSE := $(DOCKER_ENV) docker compose
PYTHON_VERSION ?= 3.13

.DEFAULT_GOAL := backend
.PHONY: backend install test frontend-dev

install:
	poetry env use $(PYTHON_VERSION)
	poetry install

test:
	poetry run python -m pytest -q

frontend-dev:
	cd frontend && npm run dev

backend:
	$(COMPOSE) up -d postgres redis minio neo4j ollama backend worker beat
