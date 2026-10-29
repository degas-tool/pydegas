# Shortcuts for the commands in README.md. make is preinstalled on the TACAS VM
# (build-essential) and on macOS with the Xcode command line tools.
IMAGE := pydegas-artifact
VENV := $(CURDIR)/libs/pydegas/.venv/bin

.PHONY: image smoke replicate venv smoke-venv replicate-venv webapp webapp-docker webapp-docker-down clean clean-docker

image:
	docker build -f Dockerfile.artifact -t $(IMAGE) .

smoke: image
	docker run --rm $(IMAGE) bash scripts/smoke_test.sh

replicate: image
	mkdir -p results
	docker run --rm -v "$(CURDIR)/results:/artifact/results" $(IMAGE) bash scripts/replicate.sh

venv:
	bash scripts/setup_venv.sh

smoke-venv: venv
	PATH="$(VENV):$$PATH" bash scripts/smoke_test.sh

replicate-venv: venv
	PATH="$(VENV):$$PATH" bash scripts/replicate.sh

webapp:
	bash scripts/web_app_local.sh

webapp-docker:
	bash scripts/web_app.sh up

webapp-docker-down:
	bash scripts/web_app.sh down

clean:
	rm -rf results .uv-bin libs/pydegas/.venv libs/degas-api/.venv libs/degas-api/degas_sessions.db

clean-docker:
	COMPOSE_FILE=compose.yaml:compose.local.yaml docker compose down --volumes --rmi local
	docker image rm -f $(IMAGE)
