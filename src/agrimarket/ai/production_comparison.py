"""Evidence-based comparison of observed Moroccan crop production."""

from agrimarket.ai.agents import _read


def production_comparison_agent() -> dict:
    """Summarize the latest recorded production and change for each crop."""
    import pandas as pd

    df = _read("faostat_morocco_production.csv")
    required = {"Item", "Year", "Unit", "Value"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"Production data needs columns: {sorted(required)}"
        )

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Item", "Year", "Value"]).copy()
    df["Year"] = df["Year"].astype(int)

    records = []
    for crop, group in df.groupby("Item", sort=True):
        group = group.sort_values("Year")
        latest = group.iloc[-1]
        previous = group.iloc[-2] if len(group) > 1 else None

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
            "Latest recorded production and change from the previous "
            "recorded year. Production volume does not establish crop "
            "suitability, profitability, or yield per hectare."
        ),
        "records": records,
    }
