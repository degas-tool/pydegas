# Artifact: pydegas and degas.dev

Artifact for the TACAS 2027 tool demonstration paper *pydegas and degas.dev: a
Library and a Web Application for Sample-Free Gradient-Based Optimization of
Probabilistic Programs* (Merttürk, Randone).

- **Paper submission number (EasyChair):** 4289
- **Artifact (permanent link):** `TODO: Zenodo DOI`
- **Source repository:** https://github.com/degas-tool/pydegas
- **Badges applied for:** Functional, Available, **Reusable**
- **Tested on:** see [Tested platforms](#tested-platforms)

## What is in this archive

| Path | Content |
|---|---|
| `libs/pydegas/` | the Python library (source, tests, documentation in `docs/`) |
| `libs/degas-api/`, `libs/degas-ui/` | the web service (FastAPI) and the browser frontend (React) of degas.dev |
| `libs/degas-ui/dist/` | the frontend, prebuilt, so that the web application runs without Node.js |
| `reference/DeGAS/` | the reference implementation of DeGAS (`frarandone/DeGAS`, revision `ee6fa12`), used as oracle for the differential tests |
| `examples/insulin_pump.py` | running example of the paper (Fig. 1, Listing 1.1) |
| `scripts/` | `smoke_test.sh`, `replicate.sh`, `case_studies.py`, `compare_insulin.py` (with the reference run `insulin_pump_reference.json`), `setup_venv.sh`, `web_app.sh`, `web_app_local.sh` |
| `Makefile` | one-command shortcuts for all steps below |
| `Dockerfile.artifact` | image for the library experiments (linux/amd64 and linux/arm64) |
| `compose.yaml`, `compose.local.yaml` | Docker Compose files of the web application |
| `LICENSE` | MIT license (allows evaluating, running and modifying the artifact) |
| `PROJECT_README.md` | README of the open-source project itself |

## Requirements

- **Docker** (any recent version with the `docker build` command; BuildKit is the default), about 4 GB of free RAM
  and 5 GB of disk. No GPU, no proprietary software. Network access is needed
  once, to download base images and the pinned Python dependencies.
- Alternative without Docker: Python >= 3.12 and network access, see
  [Without Docker](#without-docker-eg-on-the-tacas-vm).
- Works on **amd64 and arm64** hosts (Intel/AMD, Apple Silicon, ARM Linux): the
  image is built natively for the host architecture.

The TACAS VM has neither Docker nor `just` (which the project uses to run its
Docker Compose stack). For the artifact we therefore added a `Makefile` with a
shortcut for every step, a version of every step without Docker, and a way to
run the web application without Docker, Node.js and Redis (Section 4). `make`
is preinstalled on the VM and on macOS with the Xcode command line tools.

| Step | With Docker | Without Docker (TACAS VM) |
|---|---|---|
| build | `make image` | `make venv` |
| smoke test | `make smoke` | `make smoke-venv` |
| reproduce the results | `make replicate` | `make replicate-venv` |
| web application | `make webapp-docker`, `make webapp-docker-down` | `make webapp` (stop with Ctrl+C) |
| clean up | `make clean-docker` | `make clean` |

`make clean` removes what the steps without Docker create in this directory
(`results/`, the two virtual environments, the local uv binary `.uv-bin/` and
the session database of the web application). `make clean-docker` stops the
Docker Compose stack and removes its containers, volumes and images and the
image `pydegas-artifact`. uv's download cache (`~/.cache/uv`) and the Python it
downloaded (`~/.local/share/uv/python`) are outside this directory; remove them
with `uv cache clean` and `uv python uninstall 3.12` (run `make clean` last, it
removes `.uv-bin/uv`).

## 1. Build the image (once, about 5 minutes)

From the directory containing this README:

```bash
docker build -f Dockerfile.artifact -t pydegas-artifact .
```

The build installs the exact dependency versions pinned in
`libs/pydegas/uv.lock` (CPU-only PyTorch 2.12.0) and `matplotlib==3.11.2`, on
the base images `python:3.12.16-slim-bookworm` and `astral/uv:0.11.33`, both
pinned by digest in `Dockerfile.artifact`.

## 2. Smoke test (about 1 minute)

```bash
docker run --rm pydegas-artifact bash scripts/smoke_test.sh
```

It (1) runs the three-step optimization of Listings 1.2/1.3 and checks the first
step against the listing (loss 2.00063, `tOff` 15.9), (2) runs the whole test
suite (155 tests, of which 35 are differential tests against `reference/DeGAS`)
and (3) runs the three case studies for three steps against the reference.
The last line must be `SMOKE TEST PASSED`.

## 3. Reproducing the results of the paper (about 40 minutes)

```bash
mkdir -p results
docker run --rm -v "$(pwd)/results:/artifact/results" pydegas-artifact bash scripts/replicate.sh
```

(on Windows PowerShell write `${PWD}` instead of `$(pwd)`). The output is also
saved in `results/`. The script performs three experiments:

| | Claim in the paper | What to look for |
|---|---|---|
| A | Section 4, Listing 1.1 and Fig. 1/3: the optimizer moves the insulin-pump parameters from `_gTh = 150`, `_uHigh = 20` to about 128.6 and 15.0 | the run ends with `144 True 0.7823... {'gTh': 128.59..., 'uHigh': 14.98...}`, as in Listing 1.1, and the comparison prints `compared with the Apple M2 Pro run over N steps: max rel. diff of loss trace = ..., of parameter trace = ...`, both around `1e-05` or below (`scripts/compare_insulin.py` compares every step with the run on an Apple M2 Pro, `scripts/insulin_pump_reference.json`). The run stops after 10 loss changes in a row below 0.001, and the change at step 134 is 0.001 up to float32 rounding, so on some platforms the run stops one step earlier, at `143 True 0.7830... {'gTh': 128.68..., 'uHigh': 15.02...}` (in Docker on Apple Silicon); the next line of the comparison then names that step. Runtime 6 to 13 minutes (336 s native on Windows, 553 s on Linux/WSL2, 753 s in Docker on the same machine, 392 s in Docker on an Apple M2 Pro); the paper's 170 s were measured through the web application on an Apple M2 Pro. |
| B | Section 5: pydegas agrees with the reference on mixtures, moments and gradients | `155 passed`. The paper reports 32 differential test cases; the suite has since grown to 35 (marker `reference`). |
| C | Section 5: complete optimization runs on the thermostat, gearbox and PID case studies agree with the reference | three lines `max rel. diff of loss trace = ...`, all below `2.1e-05` (the bound stated in the paper); on our machine the traces were identical (`0.00e+00`). Runtime 16 to 26 minutes (thermostat 100 steps, gearbox 200, PID 500, each run with both implementations; 16 minutes natively on Linux/WSL2, 26 minutes in Docker on the same machine, 9 minutes in Docker on an Apple M2 Pro). The two implementations are run in float64, as in the reference notebooks, on the programs of the bundled web examples (`scripts/programs/`, extracted from `libs/degas-ui/src/examples.ts`), with their `signal_error` loss and hyperparameters, and classic pruning. |

Individual experiments can be run alone, inside the container
(`docker run --rm -it pydegas-artifact`) or directly:

```bash
docker run --rm pydegas-artifact python examples/insulin_pump.py          # A
docker run --rm pydegas-artifact bash -c "cd libs/pydegas && python -m pytest -q"   # B
docker run --rm pydegas-artifact python scripts/case_studies.py thermostat # C (one case)
```

## 4. The web application degas.dev (Section 3.2, Fig. 3)

Without Docker (also on the TACAS VM):

```bash
bash scripts/web_app_local.sh     # or: make webapp; then open http://localhost:3000
```

This runs the same frontend and API as the Docker Compose stack, in one
process: degas-api serves the prebuilt frontend (`libs/degas-ui/dist`, built
from `libs/degas-ui/src` with `npm ci && npm run build`; Node.js is only needed
to build it) and stores sessions in SQLite. Redis is only used for the per-client
rate limit and the cap on concurrent runs of a shared deployment (Section 3.2);
here both are off, so the header always shows every run slot free. The first
start installs the pinned dependencies of degas-api (about 1 minute, network
needed). Stop it with Ctrl+C. If port 3000 is taken, start it with
`DEGAS_API_PORT=3001`.

For the artifact, both ways of starting the web application raise two limits of
the API (see `libs/degas-api/docs/limits.md`): `Kmax` may be up to 999 instead
of 99, and a run may take 3600 s instead of 300 s.

With Docker Compose, as in the deployment, the web application is started on
the **host** (not inside the evaluation image) as three containers (UI, API,
Redis):

```bash
bash scripts/web_app.sh up        # then open http://localhost:3000
bash scripts/web_app.sh down      # stop and clean up
```

(Equivalent: `COMPOSE_FILE=compose.yaml:compose.local.yaml docker compose up -d --build`.
On Windows run the script in WSL 2 or Git Bash.) The first build takes several minutes.
API documentation is served at http://localhost:3000/docs.

In both cases the browser loads the code editor (Monaco) from
`cdn.jsdelivr.net`, so it needs network access.

Note: degas-api installs `pydegas` 0.0.1 from PyPI (see
`libs/degas-api/uv.lock`) instead of using `libs/pydegas/`. The two are the
same code: the Python files of the PyPI wheel are identical to
`libs/pydegas/src/pydegas`.

To reproduce Fig. 3:

1. Open http://localhost:3000 and select `InsulinPump` in the examples menu.
   This loads the program of Fig. 1 (left), switches the loss to `custom` with
   the `glycemic_risk` objective of Fig. 1 (right; the same text as `program`
   and `loss_src` in `examples/insulin_pump.py`), and sets optimizer Adam,
   learning rate 0.15, 150 steps, tolerance 0.001, patience 10, `classic`
   pruning, the loss arguments `idx` 0 to 17, `k` 2, `w` 2, and the initial
   parameters `_gTh` 150, `_uHigh` 20.
2. Press Run. The loss and parameter traces grow live; the run ends as
   `converged` after 145 steps, at `gTh` 128.595 and `uHigh` 14.985 (Appendix
   D). It takes about 1 to 3 minutes. The `data` button exports the run as JSON.

The web application sends no `Kmax`, so the API uses its default of 20, while
Listing 1.1 uses 100; this is why the final values differ from Listing 1.1 in
the fourth digit.

The other bundled examples (thermostat, gearbox, PID controller, bouncing
ball) are in the same menu. Tests of the web service: see
`libs/degas-api/README.md`.

## Without Docker (e.g. on the TACAS VM)

On the TACAS 2027 VM (Ubuntu, amd64 or arm64; Python and network access are
available):

```bash
bash scripts/setup_venv.sh
source libs/pydegas/.venv/bin/activate
bash scripts/smoke_test.sh
bash scripts/replicate.sh
```

The script installs a pinned `uv` locally if none is present, and `uv` downloads Python 3.12 if the system has none (so a newer system Python such as 3.14 is not used).
`libs/pydegas/docs/getting-started.md` shows how to use the library
interactively; `uv add pydegas` installs the released version from PyPI.

## Reusability

- Documentation of the library (`libs/pydegas/docs/`), the DeGASLoss language
  (`loss-dsl.md`), the web service and the UI (`libs/*/docs/`).
- Dependencies are pinned by lock files (`uv.lock`); the test suite
  (`libs/pydegas/tests`, `libs/degas-api/tests`) runs in CI.
- Any DeGAS program and any loss (built-in, Python callable or DeGASLoss) can be
  used: edit `program` and `loss_src` in `examples/insulin_pump.py`, or use the
  web application.

## Tested platforms

| Host | OS | Architecture | Method | Status |
|---|---|---|---|---|
| Windows 11 (WSL 2, 24 cores, 15 GB) | Ubuntu 24.04 | amd64 | `setup_venv.sh`, Python 3.12.3, PyTorch 2.12.0+cpu (no Docker) | smoke test and full `replicate.sh` |
| Windows 11 with Docker Desktop (WSL 2 backend) | Debian 12 in the image (`python:3.12-slim-bookworm`) | amd64 | Docker, `Dockerfile.artifact`, Python 3.12.16, PyTorch 2.12.0+cpu | smoke test and full `replicate.sh` (about 39 minutes), all results as expected |
| MacBook Pro 14" (Mac14,9), Apple M2 Pro (10 cores: 6 performance, 4 efficiency), 16 GB; Docker Desktop 24.0.5 with 5 CPUs and 8 GB assigned | macOS 26.6.2; Debian 12 in the image (`python:3.12-slim-bookworm`) | arm64 | Docker, `Dockerfile.artifact`, Python 3.12.16, PyTorch 2.12.0+cpu | smoke test (37 s) and full `replicate.sh` (16 minutes): B `155 passed`, C traces identical (`0.00e+00`); A converges one step earlier, `143 True 0.7830323576927185 {'gTh': 128.6864776611328, 'uHigh': 15.026304244995117}` (392 s); `compare_insulin.py`: max rel. diff to the Apple M2 Pro run `1.89e-05` (loss) and `8.31e-06` (parameters) over 144 steps |
| `ubuntu:26.04` container on the same MacBook Pro, as a stand-in for the TACAS VM (no Docker, no `just` inside; system Python 3.14.4) | Ubuntu 26.04.1 LTS | arm64 | `make smoke-venv` (`setup_venv.sh` installs uv 0.13.5, which downloads Python 3.12.15), `make webapp` | smoke test passed (1:40 including the installation); the web application served the UI and the API |
| the same MacBook Pro, natively | macOS 26.6.2 | arm64 | `web_app_local.sh` (no Docker), Python 3.12 from uv | web application served (on port 3101 via `DEGAS_API_PORT`); the InsulinPump example sent to the WebSocket API converged after 145 steps at `gTh` 128.595, `uHigh` 14.985, as in Appendix D (70 s) |

## License

MIT, see `LICENSE`. `reference/DeGAS/` carries its own license
(`reference/DeGAS/license.txt`).
