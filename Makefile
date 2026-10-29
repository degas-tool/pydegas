# Shortcuts for the commands in README.md. make is preinstalled on the TACAS VM
# (build-essential) and on macOS with the Xcode command line tools.
IMAGE := pydegas-artifact
VENV := $(CURDIR)/libs/pydegas/.venv/bin

.PHONY: image smoke replicate venv smoke-venv replicate-venv webapp webapp-docker webapp-docker-down

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
