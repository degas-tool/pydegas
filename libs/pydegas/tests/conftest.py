from __future__ import annotations

import hashlib
import importlib
import json
import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def make_dist():
    """Build independent float32 CPU tensors for every test and implementation."""
    torch = pytest.importorskip("torch")
    from pydegas.mixtures.distribution import Dist
    from pydegas.mixtures.gaussian_mix import GaussianMix

    def build(names, weights, means, covariances, *, implementation=None):
        dist_type = Dist if implementation is None else implementation.Dist
        mixture_type = GaussianMix if implementation is None else implementation.GaussianMix
        return dist_type(
            list(names),
            mixture_type(
                torch.tensor(weights, dtype=torch.float32).reshape(-1, 1),
                torch.tensor(means, dtype=torch.float32),
                torch.tensor(covariances, dtype=torch.float32),
            ),
        )

    return build


@pytest.fixture
def assert_same_distribution():
    torch = pytest.importorskip("torch")

    def compare(actual, expected, *, rtol=1e-5, atol=1e-6):
        assert actual.var_list == expected.var_list
        for field in ("pi", "mu", "sigma"):
            torch.testing.assert_close(
                getattr(actual.gm, field),
                getattr(expected.gm, field),
                rtol=rtol,
                atol=atol,
                msg=lambda message, field=field: f"{field}: {message}",
            )
        torch.testing.assert_close(actual.gm.mean(), expected.gm.mean(), rtol=rtol, atol=atol)
        torch.testing.assert_close(actual.gm.cov(), expected.gm.cov(), rtol=rtol, atol=atol)

    return compare


@pytest.fixture(scope="session")
def reference():
    """Import the real reference tree; never substitute pydegas for the oracle.

    The reference omits functools.partial in its assignment and truncation modules.
    Supply that standard-library import in memory only; leave algorithms and files
    unchanged. See tests/README.md for the scope of this compatibility shim.
    """
    pytest.importorskip("torch")
    source = Path(__file__).resolve().parents[3] / "DeGAS" / "src"
    if not (source / "libSOGA.py").is_file():
        pytest.fail(f"Reference source missing at {source}; run from the monorepo or use -m 'not reference'.")
    manifest = json.loads(Path(__file__).with_name("reference_manifest.json").read_text())
    for name, expected_hash in manifest["files"].items():
        actual_hash = hashlib.sha256((source / name).read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"Reference {name} differs from pinned revision {manifest['revision']}"
    names = {
        "builder": "producecfg",
        "engine": "libSOGA",
        "smoother": "smoothcfg",
        "shared": "libSOGAshared",
        "update": "libSOGAupdate",
        "truncate": "libSOGAtruncate",
        "merge": "libSOGAmerge",
        "preprocessor": "sogaPreprocessor",
        "optimization": "optimization",
    }
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(source))
        modules = {key: importlib.import_module(name) for key, name in names.items()}
        for name in manifest["files"]:
            module = sys.modules[Path(name).stem]
            assert module.__file__ is not None, f"Reference module has no source path: {name}"
            assert Path(module.__file__).resolve() == source / name, f"Wrong reference module imported: {name}"
        for key in ("update", "truncate"):
            if not hasattr(modules[key], "partial"):
                patch.setattr(modules[key], "partial", partial, raising=False)
        yield SimpleNamespace(**modules)
