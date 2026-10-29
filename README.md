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
| `reference/DeGAS/` | the reference implementation of DeGAS (`frarandone/DeGAS`, revision `ee6fa12`), used as oracle for the differential tests |
| `examples/insulin_pump.py` | running example of the paper (Fig. 1, Listing 1.1) |
| `scripts/` | `smoke_test.sh`, `replicate.sh`, `case_studies.py`, `setup_venv.sh`, `web_app.sh` |
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

## 1. Build the image (once, about 5 minutes)

From the directory containing this README:

```bash
docker build -f Dockerfile.artifact -t pydegas-artifact .
```

The build installs the exact dependency versions pinned in
`libs/pydegas/uv.lock` (CPU-only PyTorch 2.12.0) and `matplotlib==3.11.2`.

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
| A | Section 4, Listing 1.1 and Fig. 1/3: the optimizer moves the insulin-pump parameters from `_gTh = 150`, `_uHigh = 20` to about 128.6 and 15.0 | last line `144 True 0.7823... {'gTh': 128.59..., 'uHigh': 14.98...}`. Digits beyond the third may differ between CPUs and library builds. Runtime 6 to 13 minutes (336 s native on Windows, 553 s on Linux/WSL2, 753 s in Docker on the same machine); the paper's 170 s were measured through the web application on an Apple M2 Pro. |
| B | Section 5: pydegas agrees with the reference on mixtures, moments and gradients | `155 passed`. The paper reports 32 differential test cases; the suite has since grown to 35 (marker `reference`). |
| C | Section 5: complete optimization runs on the thermostat, gearbox and PID case studies agree with the reference | three lines `max rel. diff of loss trace = ...`, all below `2.1e-05` (the bound stated in the paper); on our machine the traces were identical (`0.00e+00`). Runtime 16 to 26 minutes (thermostat 100 steps, gearbox 200, PID 500, each run with both implementations; 16 minutes natively on Linux/WSL2, 26 minutes in Docker on the same machine). The two implementations are run in float64, as in the reference notebooks, on the programs of the bundled web examples (`scripts/programs/`, extracted from `libs/degas-ui/src/examples.ts`), with their `signal_error` loss and hyperparameters, and classic pruning. |

Individual experiments can be run alone, inside the container
(`docker run --rm -it pydegas-artifact`) or directly:

```bash
docker run --rm pydegas-artifact python examples/insulin_pump.py          # A
docker run --rm pydegas-artifact bash -c "cd libs/pydegas && python -m pytest -q"   # B
docker run --rm pydegas-artifact python scripts/case_studies.py thermostat # C (one case)
```

## 4. The web application degas.dev (Section 3.2, Fig. 3)

The web application is started on the **host** (not inside the evaluation image)
with Docker Compose; it builds three containers (UI, API, Redis):

```bash
bash scripts/web_app.sh up        # then open http://localhost:3000
bash scripts/web_app.sh down      # stop and clean up
```

(Equivalent: `COMPOSE_FILE=compose.yaml:compose.local.yaml docker compose up -d --build`.
On Windows run the script in WSL 2 or Git Bash.) The first build takes several minutes.
API documentation is served at http://localhost:3000/docs.

Note: the API container installs `pydegas` 0.0.1 from PyPI (see
`libs/degas-api/uv.lock`) instead of using `libs/pydegas/`. The two are the
same code: the Python files of the PyPI wheel are identical to
`libs/pydegas/src/pydegas`.

To reproduce Fig. 3:

1. Open http://localhost:3000 and click `+ new`.
2. Paste the program of Fig. 1 (left; the same text as `program` in
   `examples/insulin_pump.py`) into the program editor.
3. Select the loss `custom` and paste the `loss glycemic_risk(...)` definition
   (`loss_src` in `examples/insulin_pump.py`) into the loss editor.
4. Set optimizer Adam, learning rate 0.15, 150 steps, tolerance `1e-3`,
   patience 10, loss arguments `idx = 0,1,...,17`, `k = 2`, `w = 2`, and initial
   parameters `_gTh = 150`, `_uHigh = 20`. Press Run.
5. The loss and parameter traces grow live; the run ends as `converged` after
   about 145 steps. The `data` button exports the run as JSON (Appendix D).

The bundled examples (thermostat, gearbox, PID controller, bouncing ball) are
available from the examples menu. Tests of the web service: see
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
interactively; `pip install pydegas` installs the released version from PyPI.

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
| TODO | TODO | arm64 | Docker | TODO |

## License

MIT, see `LICENSE`. `reference/DeGAS/` carries its own license
(`reference/DeGAS/license.txt`).
