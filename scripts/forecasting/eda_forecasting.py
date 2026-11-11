"""Exploratory analysis of the crop production data used for forecasting.

Reads the processed FAOSTAT production dataset (and, when present, the raw
export and the NASA POWER annual climate file) without modifying them, then
writes summary tables and figures for the Phase 1 documentation.

Run from the repository root:

    python scripts/forecasting/eda_forecasting.py
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agrimarket.analytics.forecasting import (  # noqa: E402
    MIN_TRAINING_OBSERVATIONS,
    _get_crop_series,
)

PRODUCTION_PATH = PROJECT_ROOT / "data/processed/faostat_morocco_production.csv"
RAW_PATH = PROJECT_ROOT / "data/raw/faostat_morocco_crops.csv"
CLIMATE_PATH = PROJECT_ROOT / "data/processed/nasa_power_annual.csv"
DOCS_DIR = PROJECT_ROOT / "docs/ml_model_evaluation/EDA_yearly"

# A year-over-year change of at least a doubling or a halving.
ABRUPT_LOG_CHANGE = np.log(2.0)

FLAG_ORDER = ["A", "E", "I", "X"]
FLAG_COLORS = {
    "A": "#2a9d8f",
    "E": "#e9c46a",
    "I": "#f4a261",
    "X": "#8d99ae",
    "missing": "#d62828",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=PRODUCTION_PATH)
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--climate", type=Path, default=CLIMATE_PATH)
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    return parser.parse_args()


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        values = df[column]
        non_null = values.dropna()
        rows.append({
            "column": column,
            "dtype": str(values.dtype),
            "non_null": int(values.notna().sum()),
            "missing": int(values.isna().sum()),
            "missing_pct": round(values.isna().mean() * 100, 2),
            "unique": int(values.nunique(dropna=True)),
            "example": str(non_null.iloc[0]) if not non_null.empty else "",
        })
    return pd.DataFrame(rows)


def coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the same numeric coercion used by the forecasting code."""
    out = df.copy()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["Value"] = pd.to_numeric(out["Value"], errors="coerce")
    return out


def _spikes(log_changes: np.ndarray) -> int:
    """Count years that move abruptly away from both neighbours.

    A spike is an abrupt change into a year followed by an abrupt change of
    the opposite sign out of it. Level-based outlier scores are unreliable
    on ten-point trending series, so isolated reversals are used instead.
    """
    into, out_of = log_changes[:-1], log_changes[1:]
    return int(np.sum(
        (np.abs(into) >= ABRUPT_LOG_CHANGE)
        & (np.abs(out_of) >= ABRUPT_LOG_CHANGE)
        & (np.sign(into) != np.sign(out_of))
    ))


def _linear_trend(years: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    """Return slope as % of mean per year and the R² of a straight-line fit."""
    if len(values) < 3 or np.allclose(values, values[0]):
        return 0.0, np.nan
    slope, intercept = np.polyfit(years, values, deg=1)
    fitted = slope * years + intercept
    ss_res = float(np.sum((values - fitted) ** 2))
    ss_tot = float(np.sum((values - values.mean()) ** 2))
    return float(slope / values.mean() * 100), 1 - ss_res / ss_tot


def current_rule_status(df: pd.DataFrame, crop: str) -> str:
    """Run the forecasting module's own series validation for one crop."""
    try:
        _get_crop_series(df, crop)
    except ValueError as exc:
        return str(exc)
    return "valid"


def crop_summary(df: pd.DataFrame) -> pd.DataFrame:
    all_years = sorted(df["Year"].dropna().astype(int).unique())
    rows = []
    for crop, group in df.groupby("Item", sort=True):
        group = group.sort_values("Year")
        years = group["Year"].to_numpy(dtype=float)
        values = group["Value"].to_numpy(dtype=float)
        finite = np.isfinite(values)
        observed_years = set(group["Year"].dropna().astype(int))
        span = range(int(np.nanmin(years)), int(np.nanmax(years)) + 1)
        positive = values[finite & (values > 0)]
        log_values = np.log(positive)
        log_changes = np.diff(log_values) if len(positive) == len(values) else np.array([])
        slope_pct, r2 = _linear_trend(years[finite], values[finite])
        flags = group["Flag"].value_counts()

        rows.append({
            "crop": crop,
            "observations": int(len(group)),
            "first_year": int(np.nanmin(years)),
            "last_year": int(np.nanmax(years)),
            "missing_years_in_span": sum(1 for y in span if y not in observed_years),
            "missing_years_vs_dataset": len(set(all_years) - observed_years),
            "duplicate_years": int(group["Year"].duplicated().sum()),
            "units": ";".join(sorted(group["Unit"].dropna().astype(str).unique())),
            "non_finite_values": int((~finite).sum()),
            "zero_values": int((values == 0).sum()),
            "negative_values": int((values < 0).sum()),
            "min": float(np.nanmin(values)),
            "median": float(np.nanmedian(values)),
            "mean": float(np.nanmean(values)),
            "max": float(np.nanmax(values)),
            "std": float(np.nanstd(values, ddof=1)),
            "cv": float(np.nanstd(values, ddof=1) / np.nanmean(values)),
            "repeated_consecutive_values": int((np.diff(values) == 0).sum()),
            "constant_series": bool(np.nanmax(values) == np.nanmin(values)),
            "mean_abs_yoy_log_change": (
                float(np.mean(np.abs(log_changes))) if len(log_changes) else np.nan
            ),
            "max_abs_yoy_log_change": (
                float(np.max(np.abs(log_changes))) if len(log_changes) else np.nan
            ),
            "abrupt_changes": int((np.abs(log_changes) >= ABRUPT_LOG_CHANGE).sum()),
            "spikes": _spikes(log_changes) if len(log_changes) > 1 else 0,
            "trend_slope_pct_of_mean_per_year": slope_pct,
            "trend_r2": r2,
            "official_values": int(flags.get("A", 0)),
            "estimated_values": int(flags.get("E", 0)),
            "imputed_values": int(flags.get("I", 0)),
            "external_values": int(flags.get("X", 0)),
            "official_share": float(flags.get("A", 0) / len(group)),
            "current_rule_status": current_rule_status(df, crop),
        })
    return pd.DataFrame(rows)


def year_summary(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values(["Item", "Year"]).copy()
    ordered["log_change"] = ordered.groupby("Item")["Value"].transform(
        lambda s: np.log(s.where(s > 0)).diff()
    )
    flags = pd.crosstab(ordered["Year"], ordered["Flag"]).reindex(
        columns=FLAG_ORDER, fill_value=0
    )
    grouped = ordered.groupby("Year")
    summary = pd.DataFrame({
        "crops_observed": grouped["Item"].nunique(),
        "total_production_t": grouped["Value"].sum(),
        "median_abs_yoy_log_change": grouped["log_change"].apply(
            lambda s: s.abs().median()
        ),
        "crops_with_abrupt_change": grouped["log_change"].apply(
            lambda s: int((s.abs() >= ABRUPT_LOG_CHANGE).sum())
        ),
    })
    summary = summary.join(flags.add_prefix("flag_"))
    return summary.reset_index().rename(columns={"Year": "year"})


def flag_summary(df: pd.DataFrame) -> pd.DataFrame:
    counts = (
        df.groupby(["Flag", "Flag Description"], dropna=False)
        .size()
        .rename("observations")
        .reset_index()
        .sort_values("observations", ascending=False)
    )
    counts["share_pct"] = (counts["observations"] / len(df) * 100).round(2)
    per_crop = df.groupby("Item")["Flag"].apply(lambda s: (s == "A").mean())
    counts.attrs["crops_all_official"] = int((per_crop == 1).sum())
    counts.attrs["crops_no_official"] = int((per_crop == 0).sum())
    return counts


def eligibility_summary(crops: pd.DataFrame) -> pd.DataFrame:
    """Count crops that satisfy each entry point's minimum series length.

    Every entry point also requires a valid series (contiguous years, one
    unit, no negative or non-finite values). Rows marked hypothetical are
    not implemented; they show what alternative designs would cost.

    Rows marked implemented are the entry points as audited in commit
    20af93f. They are kept here so that this table reproduces the published
    audit results.
    """
    valid = crops["current_rule_status"].eq("valid")
    n = crops["observations"]
    m = MIN_TRAINING_OBSERVATIONS
    designs = [
        ("forecasting.evaluate_forecast(test_size=2)", "implemented",
         m + 2, "2 one-step test years"),
        ("forecasting.select_best_method(selection_test_size=2)", "implemented",
         m + 2, "2 selection years from one fixed origin"),
        ("scripts/generate_forecasts.py", "implemented",
         m + 2, "selection on last 2 years, refit on all years"),
        ("scripts/evaluate_forecasting.py", "implemented",
         m + 1, "up to 5 one-step test years"),
        ("scripts/validate_forecasting.py", "implemented",
         m + 2 + 2, "2 selection years + 2 holdout years"),
        ("rolling origin, 3 selection + 3 holdout years", "hypothetical",
         m + 3 + 3, "4 training years at first origin"),
        ("rolling origin, 5 training + 3 selection + 3 holdout years",
         "hypothetical", 5 + 3 + 3, "requires 11 annual observations"),
    ]
    rows = []
    for name, status, minimum, note in designs:
        eligible = valid & (n >= minimum)
        rows.append({
            "evaluation_design": name,
            "status": status,
            "minimum_observations": minimum,
            "eligible_crops": int(eligible.sum()),
            "excluded_crops": int((~eligible).sum()),
            "note": note,
        })
    return pd.DataFrame(rows)


def abrupt_changes(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values(["Item", "Year"]).copy()
    ordered["previous_value"] = ordered.groupby("Item")["Value"].shift()
    ordered["log_change"] = np.log(ordered["Value"] / ordered["previous_value"])
    changes = ordered.loc[ordered["log_change"].abs() >= ABRUPT_LOG_CHANGE].copy()
    changes["pct_change"] = (np.exp(changes["log_change"]) - 1) * 100
    changes = changes.rename(columns={"Item": "crop", "Year": "year", "Value": "value"})
    return changes[[
        "crop", "year", "previous_value", "value", "log_change", "pct_change", "Flag"
    ]].sort_values("log_change", key=np.abs, ascending=False)


def raw_comparison(raw_path: Path, processed: pd.DataFrame) -> pd.DataFrame:
    if not raw_path.is_file():
        return pd.DataFrame([{
            "metric": "raw_file_available",
            "value": "no",
            "detail": f"{raw_path.relative_to(PROJECT_ROOT).as_posix()} is not in this checkout",
        }])
    raw = pd.read_csv(raw_path)
    rows = [
        ("raw_file_available", "yes", ""),
        ("raw_rows", len(raw), ""),
        ("processed_rows", len(processed), ""),
        ("raw_elements", ";".join(sorted(raw["Element"].astype(str).unique())), ""),
        ("raw_missing_values", int(pd.to_numeric(raw["Value"], errors="coerce").isna().sum()), ""),
        ("raw_items", raw["Item"].nunique(), ""),
        ("processed_items", processed["Item"].nunique(), ""),
    ]
    return pd.DataFrame(rows, columns=["metric", "value", "detail"])


def climate_coverage(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    climate = pd.read_csv(path)
    return pd.DataFrame([{
        "rows": len(climate),
        "locations": climate["location"].nunique(),
        "first_year": int(climate["year"].min()),
        "last_year": int(climate["year"].max()),
        "missing_values": int(climate.isna().sum().sum()),
        "location_years_expected": climate["location"].nunique()
        * (int(climate["year"].max()) - int(climate["year"].min()) + 1),
        "used_by_forecasting": "no",
    }])


def dataset_overview(raw: pd.DataFrame, df: pd.DataFrame, crops: pd.DataFrame) -> pd.DataFrame:
    years = sorted(df["Year"].dropna().astype(int).unique())
    expected_cells = df["Item"].nunique() * len(years)
    metrics = [
        ("rows", len(raw)),
        ("columns", raw.shape[1]),
        ("crops", df["Item"].nunique()),
        ("item_codes", raw["Item Code (CPC)"].nunique()),
        ("areas", ";".join(raw["Area"].astype(str).unique())),
        ("elements", ";".join(raw["Element"].astype(str).unique())),
        ("units", ";".join(raw["Unit"].astype(str).unique())),
        ("first_year", years[0]),
        ("last_year", years[-1]),
        ("crop_year_cells_expected", expected_cells),
        ("crop_year_cells_observed", int(df[["Item", "Year"]].drop_duplicates().shape[0])),
        ("duplicate_rows", int(raw.duplicated().sum())),
        ("duplicate_crop_years", int(df.duplicated(["Item", "Year"]).sum())),
        ("missing_values_in_Value", int(df["Value"].isna().sum())),
        ("non_finite_values", int((~np.isfinite(df["Value"])).sum())),
        ("zero_values", int((df["Value"] == 0).sum())),
        ("negative_values", int((df["Value"] < 0).sum())),
        ("year_equals_year_code", bool((raw["Year"] == raw["Year Code"]).all())),
        ("series_valid_under_current_rules", int(crops["current_rule_status"].eq("valid").sum())),
        ("constant_series", int(crops["constant_series"].sum())),
        ("series_with_repeated_consecutive_values", int((crops["repeated_consecutive_values"] > 0).sum())),
        ("crops_with_abrupt_change", int((crops["abrupt_changes"] > 0).sum())),
        ("abrupt_changes_total", int(crops["abrupt_changes"].sum())),
        ("spikes_total", int(crops["spikes"].sum())),
        ("crops_with_spike", int((crops["spikes"] > 0).sum())),
        ("median_production_min_crop_t", float(crops["median"].min())),
        ("median_production_max_crop_t", float(crops["median"].max())),
        ("median_cv", float(crops["cv"].median())),
        ("median_mean_abs_yoy_log_change", float(crops["mean_abs_yoy_log_change"].median())),
        ("crops_trend_r2_at_least_0_5", int((crops["trend_r2"] >= 0.5).sum())),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------


def _save(fig, path: Path) -> None:
    fig.savefig(path, dpi=110, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)


def plot_availability_heatmap(df: pd.DataFrame, crops: pd.DataFrame, path: Path) -> None:
    years = sorted(df["Year"].astype(int).unique())
    order = crops.sort_values(["official_share", "crop"], ascending=[False, True])["crop"]
    codes = {flag: index for index, flag in enumerate(FLAG_ORDER)}
    missing_code = len(FLAG_ORDER)
    grid = (
        df.assign(code=df["Flag"].map(codes))
        .pivot_table(index="Item", columns="Year", values="code", aggfunc="first")
        .reindex(index=order, columns=years)
        .fillna(missing_code)
    )
    palette = [FLAG_COLORS[f] for f in FLAG_ORDER] + [FLAG_COLORS["missing"]]

    fig, ax = plt.subplots(figsize=(8, 15))
    ax.imshow(grid.to_numpy(), aspect="auto", cmap=ListedColormap(palette),
              vmin=-0.5, vmax=missing_code + 0.5, interpolation="nearest")
    ax.set_xticks(range(len(years)), years)
    ax.set_yticks(range(len(grid)), [c[:45] for c in grid.index], fontsize=6)
    ax.set_title("Crop × year availability, coloured by FAOSTAT flag")
    descriptions = (
        df.drop_duplicates("Flag").set_index("Flag")["Flag Description"].to_dict()
    )
    handles = [
        Patch(color=FLAG_COLORS[f], label=f"{f}: {descriptions.get(f, '')}")
        for f in FLAG_ORDER
    ] + [Patch(color=FLAG_COLORS["missing"], label="no observation")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02),
              ncol=2, fontsize=7, frameon=False)
    _save(fig, path)


def plot_series_length_and_eligibility(crops: pd.DataFrame, eligibility: pd.DataFrame,
                                       path: Path) -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4),
                                      gridspec_kw={"width_ratios": [1, 1.6]})
    lengths = crops["observations"].value_counts().sort_index()
    left.bar(lengths.index.astype(str), lengths.values, color="#2a9d8f")
    left.set_xlabel("Annual observations per crop")
    left.set_ylabel("Crops")
    left.set_title("Series length distribution")
    for x, y in zip(lengths.index.astype(str), lengths.values):
        left.annotate(str(y), (x, y), ha="center", va="bottom", fontsize=9)

    labels = [
        f"{row.evaluation_design}  (≥{row.minimum_observations})"
        for row in eligibility.itertuples()
    ]
    colors = ["#264653" if s == "implemented" else "#adb5bd" for s in eligibility["status"]]
    right.barh(labels, eligibility["eligible_crops"], color=colors)
    right.invert_yaxis()
    right.set_xlim(0, len(crops) * 1.1)
    right.set_xlabel("Eligible crops")
    right.set_title("Crops eligible per evaluation design (grey = hypothetical)")
    right.tick_params(axis="y", labelsize=7)
    for y, value in enumerate(eligibility["eligible_crops"]):
        right.annotate(str(value), (value, y), va="center", xytext=(3, 0),
                       textcoords="offset points", fontsize=8)
    fig.tight_layout()
    _save(fig, path)


def plot_observations_by_year(years: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    bottom = np.zeros(len(years))
    for flag in FLAG_ORDER:
        column = f"flag_{flag}"
        ax.bar(years["year"].astype(str), years[column], bottom=bottom,
               color=FLAG_COLORS[flag], label=flag)
        bottom += years[column].to_numpy()
    ax.set_ylabel("Crop observations")
    ax.set_title("Observations per year by FAOSTAT flag")
    ax.legend(title="Flag", fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    _save(fig, path)


def plot_missing_values(profile: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(profile["column"], profile["missing_pct"], color="#e76f51")
    ax.invert_yaxis()
    ax.set_xlim(0, 105)
    ax.set_xlabel("Missing values (%)")
    ax.set_title("Missing values per column (processed production file)")
    for y, value in enumerate(profile["missing_pct"]):
        ax.annotate(f"{value:.1f}%", (value, y), va="center", xytext=(3, 0),
                    textcoords="offset points", fontsize=8)
    _save(fig, path)


def representative_crops(crops: pd.DataFrame) -> list[tuple[str, str]]:
    by_median = crops.sort_values("median").reset_index(drop=True)
    largest = by_median["crop"].iloc[-1]
    picks = [
        ("Wheat", "default crop in the app"
         + ("; largest median production" if largest == "Wheat" else "")),
        (largest, "largest median production"),
        (by_median["crop"].iloc[len(by_median) // 2], "median-sized crop"),
        (by_median["crop"].iloc[0], "smallest median production"),
        (crops.loc[crops["mean_abs_yoy_log_change"].idxmax(), "crop"],
         "most volatile year to year"),
        (crops.loc[crops["abrupt_changes"].idxmax(), "crop"],
         "most abrupt changes"),
        (crops.loc[crops["trend_r2"].idxmax(), "crop"], "strongest linear trend"),
    ]
    constant = crops.loc[crops["constant_series"], "crop"]
    if not constant.empty:
        picks.append((constant.iloc[0], "constant series"))
    no_official = crops.loc[crops["official_share"].eq(0) & ~crops["constant_series"], "crop"]
    if not no_official.empty:
        picks.append((no_official.iloc[0], "no official values"))
    seen, unique = set(), []
    for crop, reason in picks:
        if crop in set(crops["crop"]) and crop not in seen:
            seen.add(crop)
            unique.append((crop, reason))
    return unique[:8]


def plot_representative_series(df: pd.DataFrame, picks: list[tuple[str, str]],
                               path: Path) -> None:
    columns = 4
    rows = int(np.ceil(len(picks) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=(14, 3.2 * rows), squeeze=False)
    for ax, (crop, reason) in zip(axes.flat, picks):
        series = df.loc[df["Item"] == crop].sort_values("Year")
        ax.plot(series["Year"], series["Value"], marker="o", color="#264653")
        for flag in FLAG_ORDER:
            subset = series.loc[series["Flag"] == flag]
            ax.scatter(subset["Year"], subset["Value"], color=FLAG_COLORS[flag],
                       zorder=3, s=28)
        ax.axvspan(2022.5, 2024.5, color="#adb5bd", alpha=0.25, lw=0)
        ax.set_title(f"{crop[:38]}\n({reason})", fontsize=9)
        ax.tick_params(labelsize=7)
        ax.ticklabel_format(axis="y", style="sci", scilimits=(-3, 4))
    for ax in list(axes.flat)[len(picks):]:
        ax.axis("off")
    fig.suptitle("Representative production series (t); shaded = 2023–2024, "
                 "the final two years used as holdout/selection windows", fontsize=10)
    handles = [Patch(color=FLAG_COLORS[f], label=f) for f in FLAG_ORDER]
    fig.tight_layout()
    fig.legend(handles=handles, title="Flag", loc="upper center",
               bbox_to_anchor=(0.5, 0.0), ncol=4, fontsize=8, frameon=False)
    _save(fig, path)


def plot_production_distribution(df: pd.DataFrame, crops: pd.DataFrame, path: Path) -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4))
    left.hist(np.log10(df["Value"]), bins=30, color="#2a9d8f")
    left.set_xlabel("log10(production, t)")
    left.set_ylabel("Crop-year observations")
    left.set_title("All production values")

    right.scatter(crops["median"], crops["cv"], color="#264653", s=18)
    right.set_xscale("log")
    right.set_xlabel("Median annual production per crop (t, log scale)")
    right.set_ylabel("Coefficient of variation")
    right.set_title("Production scale vs. variability per crop")
    for row in crops.nlargest(4, "cv").itertuples():
        right.annotate(row.crop[:25], (row.median, row.cv), fontsize=7,
                       xytext=(4, 2), textcoords="offset points")
    fig.tight_layout()
    _save(fig, path)


def plot_yoy_changes(df: pd.DataFrame, years: pd.DataFrame, path: Path) -> None:
    ordered = df.sort_values(["Item", "Year"]).copy()
    ordered["log_change"] = ordered.groupby("Item")["Value"].transform(
        lambda s: np.log(s).diff()
    )
    changes = ordered.dropna(subset=["log_change"])

    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4))
    clipped = changes["log_change"].clip(-1.5, 1.5)
    left.hist(clipped, bins=40, color="#e76f51")
    for x in (-ABRUPT_LOG_CHANGE, ABRUPT_LOG_CHANGE):
        left.axvline(x, color="black", ls="--", lw=0.8)
    left.set_xlabel("Year-over-year log change (clipped to ±1.5)")
    left.set_ylabel("Crop-year changes")
    left.set_title("Distribution of annual changes (dashed = doubling/halving)")

    data = [changes.loc[changes["Year"] == y, "log_change"] for y in years["year"][1:]]
    right.boxplot(data, tick_labels=[str(y) for y in years["year"][1:]],
                  showfliers=False)
    right.axhline(0, color="grey", lw=0.6)
    right.set_ylabel("Year-over-year log change")
    right.set_title("Annual changes by year (whiskers 1.5 IQR, outliers hidden)")
    right.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    _save(fig, path)


def plot_trend_strength(crops: pd.DataFrame, path: Path) -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4))
    left.hist(crops["trend_r2"].dropna(), bins=20, range=(0, 1), color="#264653")
    left.set_xlabel("R² of a straight-line fit over 2015–2024")
    left.set_ylabel("Crops")
    left.set_title("How linear are the series?")

    right.hist(crops["official_share"] * 100, bins=10, range=(0, 100), color="#2a9d8f")
    right.set_xlabel("Share of official (flag A) values per crop (%)")
    right.set_ylabel("Crops")
    right.set_title("Data provenance per crop")
    fig.tight_layout()
    _save(fig, path)


# --------------------------------------------------------------------------


def write_table(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, float_format="%.4f", lineterminator="\n")


def main() -> None:
    args = parse_args()
    figures_dir = args.output_dir / "figures"
    results_dir = args.output_dir / "results"
    figures_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.data)
    df = coerce(raw)

    profile = column_profile(raw)
    crops = crop_summary(df)
    years = year_summary(df)
    flags = flag_summary(df)
    eligibility = eligibility_summary(crops)
    changes = abrupt_changes(df)
    overview = dataset_overview(raw, df, crops)
    overview = pd.concat([overview, pd.DataFrame([
        ("crops_all_official", flags.attrs["crops_all_official"]),
        ("crops_no_official", flags.attrs["crops_no_official"]),
    ], columns=["metric", "value"])], ignore_index=True)

    write_table(overview, results_dir / "dataset_overview.csv")
    write_table(profile, results_dir / "column_profile.csv")
    write_table(crops, results_dir / "crop_series_summary.csv")
    write_table(years, results_dir / "year_summary.csv")
    write_table(flags, results_dir / "flag_summary.csv")
    write_table(eligibility, results_dir / "evaluation_eligibility.csv")
    write_table(changes, results_dir / "abrupt_changes.csv")
    write_table(raw_comparison(args.raw, raw), results_dir / "raw_vs_processed.csv")
    climate = climate_coverage(args.climate)
    if not climate.empty:
        write_table(climate, results_dir / "climate_coverage.csv")

    picks = representative_crops(crops)
    plot_availability_heatmap(df, crops, figures_dir / "availability_heatmap.png")
    plot_series_length_and_eligibility(crops, eligibility,
                                       figures_dir / "series_length_and_eligibility.png")
    plot_observations_by_year(years, figures_dir / "observations_by_year.png")
    plot_missing_values(profile, figures_dir / "missing_values.png")
    plot_representative_series(df, picks, figures_dir / "representative_series.png")
    plot_production_distribution(df, crops, figures_dir / "production_distribution.png")
    plot_yoy_changes(df, years, figures_dir / "yoy_changes.png")
    plot_trend_strength(crops, figures_dir / "trend_strength_and_provenance.png")

    print(overview.to_string(index=False))
    print("\nEligibility:")
    print(eligibility[["evaluation_design", "minimum_observations",
                       "eligible_crops"]].to_string(index=False))
    print("\nRepresentative crops:", ", ".join(c for c, _ in picks))
    print(f"\nTables: {results_dir}")
    print(f"Figures: {figures_dir}")


if __name__ == "__main__":
    main()
