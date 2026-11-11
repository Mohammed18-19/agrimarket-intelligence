"""Evaluate YearlyModel on the annual FAOSTAT crop production data.

    python scripts/evaluate_yearly.py                # validation years only
    python scripts/evaluate_yearly.py --final-test   # the reserved holdout

The default run never reads the final two years. Use --final-test only to
report a model that was already chosen. Never use its scores to choose one.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agrimarket.evaluation.evaluation import (  # noqa: E402
    EvaluationSettings,
    evaluate,
    format_summary,
    new_run_dir,
    save_outputs,
)
from agrimarket.evaluation.models import YearlyModel  # noqa: E402
from agrimarket.evaluation.tracking import log_experiment  # noqa: E402

FREQUENCY = "yearly"
DATA_PATH = ROOT / "data/processed/faostat_morocco_production.csv"
TARGET_NAME = "production"
METRICS = ("mae", "rmse", "mase")
HORIZON = 1  # years ahead
SETTINGS = EvaluationSettings(min_train_size=4, holdout_size=2)


def load_yearly_data(path):
    """Adapt the FAOSTAT columns to entity_id, timestamp and target."""
    raw = pd.read_csv(path)
    units = sorted(raw["Unit"].astype(str).unique())

    # Provenance of a crop: official only, no official value, or mixed.
    # It is a label for reporting; models never see it.
    official = raw["Flag"].eq("A").groupby(raw["Item"]).mean()
    provenance = official.map(
        lambda share: "official" if share == 1 else "no_official" if share == 0 else "mixed"
    )

    data = pd.DataFrame({
        "entity_id": raw["Item"],
        "timestamp": pd.to_datetime(raw["Year"].astype(int).astype(str) + "-01-01"),
        "target": raw["Value"],
        "flag": raw["Flag"],
        "group": raw["Item"].map(provenance),
    })
    return data, ",".join(units)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--final-test", action="store_true",
                        help="score the reserved final holdout instead of the validation years")
    args = parser.parse_args()
    stage = "holdout" if args.final_test else "validation"
    if args.final_test:
        print("Holdout scores are for final reporting only, not for choosing a model.")

    data, unit = load_yearly_data(DATA_PATH)
    model = YearlyModel()
    result = evaluate(data, model, FREQUENCY, HORIZON, SETTINGS, METRICS, stage)

    run_dir = save_outputs(result, new_run_dir(FREQUENCY))
    run_id = log_experiment(result, model, DATA_PATH, run_dir, TARGET_NAME, unit)

    print(f"\nModel: {type(model).__name__} {model.get_params()} - {model.describe()}")
    print(format_summary(result))
    print(f"\nFiles:  {run_dir}")
    print(f"MLflow: experiment agrimarket-{FREQUENCY}, run {run_id}")


if __name__ == "__main__":
    main()
