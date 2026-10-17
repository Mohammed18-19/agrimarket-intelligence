import pandas as pd
import pytest

from agrimarket.ingestion.faostat import (
    FAOSTAT_REQUIRED_COLUMNS,
    load_faostat_csv,
)


def valid_faostat_data():
    return pd.DataFrame({
        "Area": ["Morocco"],
        "Item": ["Wheat"],
        "Element": ["Production"],
        "Year": [2024],
        "Unit": ["t"],
        "Value": [100.0],
        "Flag": [""],
        "Flag Description": [""],
    })


def test_loads_valid_faostat_csv(tmp_path):
    path = tmp_path / "faostat.csv"
    expected = valid_faostat_data()
    expected.to_csv(path, index=False)

    result = load_faostat_csv(path)

    assert len(result) == 1
    assert list(FAOSTAT_REQUIRED_COLUMNS) == [
        "Area", "Item", "Element", "Year",
        "Unit", "Value", "Flag", "Flag Description",
    ]
    assert result.loc[0, "Item"] == "Wheat"


def test_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_faostat_csv(tmp_path / "missing.csv")


def test_rejects_csv_missing_required_columns(tmp_path):
    path = tmp_path / "incomplete.csv"
    pd.DataFrame({"Item": ["Wheat"]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required columns"):
        load_faostat_csv(path)


def test_rejects_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")

    with pytest.raises(ValueError, match="empty"):
        load_faostat_csv(path)


def test_rejects_csv_with_headers_but_no_rows(tmp_path):
    path = tmp_path / "no_rows.csv"
    valid_faostat_data().iloc[0:0].to_csv(path, index=False)

    with pytest.raises(ValueError, match="no data rows"):
        load_faostat_csv(path)
