"""Evidence-based comparison of observed Moroccan crop production."""

import math

import pandas as pd

from agrimarket.ai.agents import _read


def production_comparison_agent() -> dict:
    """Compare crop production using consecutive years and matching units."""
    df = _read("faostat_morocco_production.csv")
    required = {"Item", "Year", "Unit", "Value"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"Production data needs columns: {sorted(required)}"
        )

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Item", "Year", "Unit", "Value"]).copy()

    df = df[
        df["Year"].mod(1).eq(0)
        & df["Value"].map(
            lambda value: math.isfinite(float(value))
        )
    ].copy()
    df["Year"] = df["Year"].astype(int)
    df["Item"] = df["Item"].astype(str).str.strip()
    df["Unit"] = df["Unit"].astype(str).str.strip()
    df = df[(df["Item"] != "") & (df["Unit"] != "")]

    records = []
    for crop, group in df.groupby("Item", sort=True):
        group = group.sort_values("Year")
        latest = group.iloc[-1]

        # Only compare against the immediately preceding calendar year
        # and only when the units match.
        candidates = group[
            (group["Year"] == int(latest["Year"]) - 1)
            & (group["Unit"] == latest["Unit"])
        ]
        previous = candidates.iloc[-1] if not candidates.empty else None

        change = None
        change_pct = None
        if previous is not None:
            change = float(latest["Value"] - previous["Value"])
            if previous["Value"] != 0:
                change_pct = float(change / previous["Value"] * 100)

        records.append({
            "crop": str(crop),
            "first_year": int(group["Year"].min()),
            "latest_year": int(latest["Year"]),
            "observations": int(len(group)),
            "latest_production": float(latest["Value"]),
            "previous_year": (
                int(previous["Year"]) if previous is not None else None
            ),
            "previous_year_production": (
                float(previous["Value"]) if previous is not None else None
            ),
            "change": change,
            "change_percentage": change_pct,
            "unit": str(latest["Unit"]),
        })

    if not records:
        return {
            "agent": "production_comparison",
            "status": "no_data",
            "crop_count": 0,
            "records": [],
        }

    return {
        "agent": "production_comparison",
        "status": "ok",
        "crop_count": len(records),
        "comparison_basis": (
            "Year-over-year changes are reported only when observations "
            "exist for consecutive calendar years in matching units. "
            "Production volume does not establish crop suitability, "
            "profitability, or yield per hectare."
        ),
        "records": records,
    }
