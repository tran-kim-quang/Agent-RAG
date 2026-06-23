LOCAL_UID := $(shell id -u)
LOCAL_GID := $(shell id -g)
DOCKER_ENV := LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID)
COMPOSE := $(DOCKER_ENV) docker compose
GPU_PROFILE ?= $(shell \
	if command -v lspci >/dev/null 2>&1 && lspci | grep -Eqi 'NVIDIA'; then \
		printf '%s' nvidia; \
	elif command -v lspci >/dev/null 2>&1 && lspci | grep -Eqi 'AMD|Radeon|Advanced Micro Devices'; then \
		printf '%s' amd; \
	elif command -v lspci >/dev/null 2>&1 && lspci | grep -Eqi 'Intel|Arc'; then \
		printf '%s' intel; \
	else \
		printf '%s' cpu; \
	fi)
OLLAMA_SERVICE := ollama-$(GPU_PROFILE)

.DEFAULT_GOAL := backend
.PHONY: backend detect-gpu

detect-gpu:
	@printf 'Detected backend profile: %s\n' "$(GPU_PROFILE)"
	@printf 'Using Ollama service: %s\n' "$(OLLAMA_SERVICE)"

backend: detect-gpu
	$(COMPOSE) --profile $(GPU_PROFILE) up -d neo4j $(OLLAMA_SERVICE) backend
