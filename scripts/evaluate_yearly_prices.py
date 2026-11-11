"""Evaluate YearlyPriceModel on annual FAOSTAT producer prices for Morocco.

    python scripts/evaluate_yearly_prices.py                    # validation years only
    python scripts/evaluate_yearly_prices.py --method drift     # another baseline
    python scripts/evaluate_yearly_prices.py --final-test       # the reserved holdout

The default run never reads the final two years. Use --final-test only to
report a model that was already chosen. Never use its scores to choose one.

Prices are in USD per tonne, one series per crop, and are never combined
across crops. Results go to their own MLflow experiment, so they are not
mixed with the production-quantity runs.
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
from agrimarket.evaluation.models import YearlyPriceModel  # noqa: E402
from agrimarket.evaluation.tracking import log_experiment  # noqa: E402

FREQUENCY = "yearly"
EXPERIMENT_NAME = "agrimarket-yearly-prices"
RUN_FOLDER = "yearly_prices"
DATA_PATH = ROOT / "data/raw/faostat_morocco_producer_prices_annual.csv"
TARGET_NAME = "producer_price"
METRICS = ("mae", "rmse", "mase")
HORIZON = 1  # years ahead
SETTINGS = EvaluationSettings(min_train_size=4, holdout_size=2)

REQUIRED_COLUMNS = ["Area", "Element", "Item", "Year", "Months", "Value", "Flag"]


def load_price_data(path):
    """Adapt the FAOSTAT producer price columns to entity_id, timestamp and target.

    Returns the data and the price unit. Fails if the file mixes areas,
    price elements (currencies or units) or periods, because a single series
    must never combine them.
    """
    raw = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")

    for column in ("Area", "Element"):
        if raw[column].nunique() != 1:
            raise ValueError(f"expected one {column} value, found {sorted(raw[column].unique())}")
    if not raw["Months"].eq("Annual value").all():
        raise ValueError("this script is for annual values; the file has other periods")

    # "Producer Price (USD/tonne)" -> "USD/tonne"
    element = raw["Element"].iloc[0]
    unit = element[element.index("(") + 1:element.rindex(")")]

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
    return data, unit


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--method", choices=YearlyPriceModel.METHODS, default="naive",
                        help="baseline to evaluate (default: naive)")
    parser.add_argument("--final-test", action="store_true",
                        help="score the reserved final holdout instead of the validation years")
    args = parser.parse_args()
    stage = "holdout" if args.final_test else "validation"
    if args.final_test:
        print("Holdout scores are for final reporting only, not for choosing a model.")

    data, unit = load_price_data(DATA_PATH)
    model = YearlyPriceModel(args.method)
    result = evaluate(data, model, FREQUENCY, HORIZON, SETTINGS, METRICS, stage)

    run_dir = save_outputs(result, new_run_dir(RUN_FOLDER))
    run_id = log_experiment(
        result, model, DATA_PATH, run_dir, TARGET_NAME, unit,
        experiment_name=EXPERIMENT_NAME,
    )

    print(f"\nModel: {type(model).__name__} {model.get_params()} - {model.describe()}")
    print(f"Price unit: {unit}")
    print(format_summary(result))
    print(f"\nFiles:  {run_dir}")
    print(f"MLflow: experiment {EXPERIMENT_NAME}, run {run_id}")


if __name__ == "__main__":
    main()
