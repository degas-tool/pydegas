from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")


def make_run(**kwargs):
    from pydegas.cfg.builder import from_text
    from pydegas.optimize import OptimizationRun

    options = {"optimizer": "SGD", "optimizer_kwargs": {"lr": 0.1}, "tolerance": None, **kwargs}
    return OptimizationRun(from_text("x = _mu;"), {"mu": 1.0}, lambda dist: dist.gm.mean().square().sum(), **options)


def test_step_records_pre_update_loss_and_post_update_parameters():
    run = make_run()
    first = run.step(0)
    assert first.loss == pytest.approx(1.0)
    assert first.params["mu"] == pytest.approx(0.8)
    assert first.dist.gm.mean().item() == pytest.approx(1.0)
    second = run.step(1)
    assert second.loss == pytest.approx(0.64)
    assert second.params["mu"] == pytest.approx(0.64)
    assert first.dist.gm.mean().item() == pytest.approx(1.0)
    assert first.params["mu"] == pytest.approx(0.8)
    assert not first.dist.gm.mu.requires_grad
    assert first.dist.gm.mu.data_ptr() != second.dist.gm.mu.data_ptr()


def test_generator_matches_eager_run():
    eager = make_run().run(5)
    streamed = list(make_run().run_generator(5))
    assert [r.step for r in streamed] == list(range(5))
    assert [r.loss for r in streamed] == pytest.approx([r.loss for r in eager])
    assert [r.params["mu"] for r in streamed] == pytest.approx([r.params["mu"] for r in eager])


def test_callback_stops_after_yielding_the_requested_step():
    seen = []

    def stop(result):
        seen.append(result.step)
        return result.step == 2

    results = make_run(on_step=stop).run(10)
    assert seen == [0, 1, 2]
    assert [r.step for r in results] == seen


def test_convergence_waits_for_full_patience_window():
    results = make_run(optimizer_kwargs={"lr": 0.0}, tolerance=1e-8, patience=2).run(10)
    assert len(results) == 3
    assert [r.converged for r in results] == [False, False, True]


def test_none_tolerance_disables_early_stopping():
    results = make_run(optimizer_kwargs={"lr": 0.0}, patience=2).run(10)
    assert len(results) == 10
    assert not any(r.converged for r in results)


def test_optimizer_class_matches_registered_name():
    by_name = make_run().run(3)
    by_class = make_run(optimizer=torch.optim.SGD).run(3)
    assert [r.params["mu"] for r in by_class] == pytest.approx([r.params["mu"] for r in by_name])


def test_run_does_not_print_or_write_distribution_statistics(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    make_run().run(3)
    output = capsys.readouterr()
    assert output.out == output.err == ""
    assert list(tmp_path.iterdir()) == []


def test_cached_assignment_tree_does_not_reuse_parameter_bindings():
    from pydegas.cfg.builder import from_text
    from pydegas.semantics.engine import start_soga

    cfg = from_text("x = _mu;")
    first = start_soga(cfg, {"mu": torch.tensor(1.0)})
    second = start_soga(cfg, {"mu": torch.tensor(3.0)})
    assert first.gm.mean().item() == pytest.approx(1.0)
    assert second.gm.mean().item() == pytest.approx(3.0)
