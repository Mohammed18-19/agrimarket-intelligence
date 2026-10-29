"""Specialized, data-grounded agricultural analysis agents."""

import os
from pathlib import Path

import pandas as pd


def _data_path(filename: str) -> Path:
    root = Path(
        os.environ.get("AGRIMARKET_PROJECT_ROOT", Path.cwd())
    ).resolve()
    return root / "data" / "processed" / filename


def _read(filename: str) -> pd.DataFrame:
    path = _data_path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.read_csv(path)


def _records(df: pd.DataFrame, limit: int = 20) -> list[dict]:
    """Return JSON-friendly records."""
    return (
        df.head(limit)
        .astype(object)
        .where(pd.notna(df.head(limit)), None)
        .to_dict(orient="records")
    )


def production_agent(crop: str | None = None) -> dict:
    """Retrieve crop history or a national overview without mixing crops."""
    df = _read("faostat_morocco_production.csv")
    required = {"Item", "Year", "Unit", "Value"}
    if not required.issubset(df.columns):
        raise ValueError(f"Production data needs columns: {sorted(required)}")

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Item", "Year", "Unit", "Value"]).copy()
    df = df[
        df["Year"].mod(1).eq(0)
        & df["Value"].map(lambda value: pd.notna(value) and abs(float(value)) != float("inf"))
    ].copy()
    df["Year"] = df["Year"].astype(int)
    df["Item"] = df["Item"].astype(str).str.strip()
    df["Unit"] = df["Unit"].astype(str).str.strip()
    df = df[(df["Item"] != "") & (df["Unit"] != "")]

    if crop:
        requested = crop.strip().casefold()
        df = df[df["Item"].str.casefold() == requested]

    if df.empty:
        return {
            "agent": "production",
            "status": "no_data",
            "crop": crop,
            "records": [],
        }

    if not crop:
        # A national overview must not produce a single-crop time-series metric.
        latest_per_crop = (
            df.sort_values(["Item", "Year"])
            .groupby("Item", sort=True, as_index=False)
            .tail(1)
            .sort_values("Item")
        )
        return {
            "agent": "production",
            "status": "ok",
            "scope": "latest_record_per_crop",
            "crop": None,
            "crops_count": int(latest_per_crop["Item"].nunique()),
            "observations": int(len(df)),
            "first_year": int(df["Year"].min()),
            "latest_year": int(df["Year"].max()),
            "records": _records(latest_per_crop, limit=len(latest_per_crop)),
            "comparison_note": (
                "This is a national crop overview, not a single-crop "
                "year-over-year comparison."
            ),
        }

    df = df.sort_values(["Year", "Unit"]).reset_index(drop=True)
    latest = df.iloc[-1]
    previous_candidates = df[
        (df["Year"] == int(latest["Year"]) - 1)
        & (df["Unit"] == latest["Unit"])
    ]
    previous = previous_candidates.iloc[-1] if not previous_candidates.empty else None

    change = None
    change_pct = None
    if previous is not None:
        change = float(latest["Value"] - previous["Value"])
        if previous["Value"] != 0:
            change_pct = float(change / previous["Value"] * 100)

    return {
        "agent": "production",
        "status": "ok",
        "scope": "crop_history",
        "crop": str(latest["Item"]),
        "observations": int(len(df)),
        "first_year": int(df["Year"].min()),
        "latest_year": int(latest["Year"]),
        "latest_production": float(latest["Value"]),
        "unit": str(latest["Unit"]),
        "previous_year": int(previous["Year"]) if previous is not None else None,
        "previous_year_production": float(previous["Value"]) if previous is not None else None,
        "change": change,
        "change_percentage": change_pct,
        "records": _records(df.sort_values("Year", ascending=False), limit=len(df)),
    }


def climate_agent(location: str | None = None) -> dict:
    """Return a complete location history or the latest national overview."""
    df = _read("nasa_power_annual.csv")
    required = {
        "location", "year", "mean_temperature_c", "total_precipitation"
    }
    if not required.issubset(df.columns):
        raise ValueError(f"Climate data needs columns: {sorted(required)}")

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"]).copy()
    df["year"] = df["year"].astype(int)

    if location:
        df = df[
            df["location"].astype(str).str.casefold()
            == location.strip().casefold()
        ]

    if df.empty:
        return {
            "agent": "climate",
            "status": "no_data",
            "records": [],
            "requested_location": location,
        }

    df = df.sort_values(["year", "location"])
    first_year = int(df["year"].min())
    latest_year = int(df["year"].max())

    numeric = [
        col for col in (
            "mean_temperature_c",
            "mean_daily_max_temperature_c",
            "mean_daily_min_temperature_c",
            "total_precipitation",
            "mean_daily_solar_radiation",
        ) if col in df.columns
    ]

    averages = (
        df.groupby("location")[numeric]
        .mean()
        .round(3)
        .reset_index()
        .to_dict(orient="records")
    )

    if location:
        records_df = df.sort_values("year", ascending=False)
        records_scope = "full_location_history"
    else:
        records_df = df[df["year"] == latest_year].sort_values("location")
        records_scope = "latest_year_all_locations"

    return {
        "agent": "climate",
        "status": "ok",
        "locations": sorted(df["location"].astype(str).unique().tolist()),
        "years": [first_year, latest_year],
        "latest_year": latest_year,
        "records_scope": records_scope,
        "records_count": len(records_df),
        "averages_period": f"{first_year}-{latest_year}",
        "averages_description": (
            "These are per-location averages across the entire available "
            f"{first_year}-{latest_year} period, not values for one year."
        ),
        "annual_averages": averages,
        "records": _records(records_df, limit=len(records_df)),
        "interpretation_limit": (
            "Climate observations alone do not establish crop suitability "
            "or prove that climate caused a production change."
        ),
    }

def forecasting_agent(crop: str | None = None) -> dict:
    """Retrieve existing forecasts and evaluation evidence."""
    forecasts = _read("crop_production_forecasts.csv")
    crop_column = "crop" if "crop" in forecasts.columns else "Item"

    if crop_column not in forecasts.columns:
        raise ValueError("Forecast dataset has no crop identifier column")

    if crop:
        forecasts = forecasts[
            forecasts[crop_column].astype(str).str.casefold()
            == crop.casefold()
        ]

    if forecasts.empty:
        return {"agent": "forecasting", "status": "no_data", "records": []}

    result = {
        "agent": "forecasting",
        "status": "ok",
        "crop": crop,
        "records": _records(forecasts),
        "evaluation": [],
        "limitations": (
            "Forecasts are model outputs, not guaranteed future production."
        ),
    }

    evaluation_path = _data_path("forecast_evaluation.csv")
    if evaluation_path.is_file():
        evaluation = pd.read_csv(evaluation_path)
        if crop and "crop" in evaluation.columns:
            evaluation = evaluation[
                evaluation["crop"].astype(str).str.casefold()
                == crop.casefold()
            ]
        result["evaluation"] = _records(evaluation)

    return result


def validation_agent(evidence: dict) -> dict:
    """Check evidence structure, not the factual correctness of model prose."""
    issues = []

    base = {
        "agent": "validation",
        "validation_scope": "evidence_structure_only",
        "answer_verified": False,
        "note": (
            "This check evaluates tool evidence structure and availability. "
            "It does not verify numerical claims in the generated answer."
        ),
    }

    if not isinstance(evidence, dict) or not evidence:
        return {
            **base,
            "status": "insufficient_evidence",
            "issues": ["No evidence was provided."],
            "approved": False,
            "agents_with_usable_data": 0,
        }

    successful = 0
    for name, result in evidence.items():
        if not isinstance(result, dict):
            issues.append(f"{name}: result is not a structured object.")
            continue

        status = result.get("status")
        if status != "ok":
            issues.append(f"{name}: status is {status or 'missing'}.")
            continue

        successful += 1

        records = result.get("records")
        averages = result.get("annual_averages")

        if not isinstance(records, list):
            issues.append(f"{name}: records must be a list.")
        elif not records and not averages:
            issues.append(f"{name}: no supporting records were returned.")
        elif any(not isinstance(record, dict) for record in records):
            issues.append(f"{name}: one or more records are not structured objects.")

        if averages is not None and not isinstance(averages, list):
            issues.append(f"{name}: annual_averages must be a list.")

    if successful == 0:
        issues.append("No agent returned usable evidence.")

    approved = successful > 0 and not issues
    return {
        **base,
        "status": "ok" if approved else "needs_review",
        "issues": issues,
        "approved": approved,
        "agents_with_usable_data": successful,
    }
