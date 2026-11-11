"""Log one evaluation to a local MLflow database. One run per execution.

``evaluation.py`` does not import this module, so evaluation works without
MLflow. Only the ``scripts/evaluate_*.py`` scripts call ``log_experiment``.

Run the MLflow web interface from the repository root with::

    mlflow ui --backend-store-uri sqlite:///mlflow.db
"""

import hashlib
import inspect
import json
import math
import os
import subprocess
from pathlib import Path

# Some Windows Application Control policies block SQLAlchemy's compiled
# extension, which MLflow's SQLite store imports. SQLAlchemy has a pure
# Python fallback that is selected by this variable. It must be set before
# SQLAlchemy is imported, and it only affects speed. The second variable
# silences an informational message that MLflow prints on import.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import mlflow  # noqa: E402

from agrimarket.evaluation.evaluation import (  # noqa: E402
    PROJECT_ROOT,
    TRAINING_SCOPE,
    EvaluationResult,
)

# The database lives in the repository root, whatever the working directory.
TRACKING_URI = f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}"
ARTIFACT_ROOT = PROJECT_ROOT / "mlartifacts"
EXPERIMENTS = {
    "daily": "agrimarket-daily",
    "weekly": "agrimarket-weekly",
    "monthly": "agrimarket-monthly",
    "yearly": "agrimarket-yearly",
}


def file_hash(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_info() -> dict:
    def git(*args):
        try:
            return subprocess.run(
                ["git", *args], cwd=PROJECT_ROOT, capture_output=True,
                text=True, check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    commit, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    return {
        "git_commit": commit or "unknown",
        "git_uncommitted_changes": "unknown" if status is None else str(bool(status)),
    }


def _relative(path) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _experiment_id(name: str, artifact_root) -> str:
    existing = mlflow.get_experiment_by_name(name)
    if existing is not None:
        return existing.experiment_id
    location = (Path(artifact_root) / name).resolve().as_uri()
    return mlflow.create_experiment(name, artifact_location=location)


def log_experiment(
    result: EvaluationResult,
    model,
    dataset_path,
    run_dir,
    target_name: str,
    target_unit: str,
    tracking_uri: str = TRACKING_URI,
    artifact_root=ARTIFACT_ROOT,
    run_name: str | None = None,
    experiment_name: str | None = None,
) -> str:
    """Create a new MLflow run for ``result`` and return its run id.

    ``run_dir`` is the directory written by ``evaluation.save_outputs``. Its
    files, plus a snapshot of the model's class source and a metadata file,
    are logged as artifacts. The experiment defaults to the one for the
    frequency. Pass ``experiment_name`` to keep a different target, such as
    prices, in its own experiment.
    """
    run_dir = Path(run_dir)
    source = inspect.getsource(type(model))
    (run_dir / "model_source.py").write_text(source, encoding="utf-8")

    model_params = model.get_params()
    d, s = result.diagnostics, result.settings
    params = {
        "model_class": type(model).__name__,
        "model_description": getattr(model, "describe", lambda: type(model).__name__)(),
        **{f"model.{key}": value for key, value in model_params.items()},
        "frequency": result.frequency,
        "horizon": result.horizon,
        "training_scope": TRAINING_SCOPE,
        "evaluation_strategy": "expanding window, refitted at every origin",
        "evaluation_stage": result.stage,
        "metrics": ",".join(result.metric_names),
        "min_train_size": s.min_train_size,
        "holdout_size": s.holdout_size,
        "random_seed": model_params.get("random_seed", "not applicable"),
        "target_name": target_name,
        "target_unit": target_unit,
        "dataset_path": _relative(dataset_path),
        "dataset_hash": file_hash(dataset_path),
        "model_source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        **git_info(),
        "train_start": d["train_start"],
        "first_train_end": d["first_train_end"],
        "scored_start": d["scored_start"],
        "scored_end": d["scored_end"],
        "holdout_start": d["holdout_start"],
        "holdout_end": d["holdout_end"],
        "holdout_used": d["holdout_used"],
    }
    params = {key: str(value) for key, value in params.items()}

    # Undefined metrics (NaN) are left out instead of being logged as numbers.
    metrics = {
        f"{result.stage}_{key}": float(value)
        for key, value in result.aggregates.items()
        if math.isfinite(float(value))
    }

    (run_dir / "experiment_metadata.json").write_text(
        json.dumps({"params": params, "metrics": metrics}, indent=2),
        encoding="utf-8",
    )

    mlflow.set_tracking_uri(tracking_uri)
    experiment_id = _experiment_id(
        experiment_name or EXPERIMENTS[result.frequency], artifact_root
    )
    name = run_name or f"{type(model).__name__} {result.stage}"
    with mlflow.start_run(experiment_id=experiment_id, run_name=name) as run:
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)

        # Only real loss histories are logged. Deterministic baselines have none.
        # With one fit per entity and window, this is the history of the last fit.
        history = getattr(model, "loss_history", None)
        if isinstance(history, dict):
            for loss_name, values in history.items():
                for step, value in enumerate(values):
                    if math.isfinite(float(value)):
                        mlflow.log_metric(f"loss.{loss_name}", float(value), step=step)

        mlflow.log_artifacts(str(run_dir))
        return run.info.run_id
