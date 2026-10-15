
from unittest.mock import Mock, patch

import pytest
import requests

from agrimarket.ingestion.nasa_power import (
    fetch_nasa_power_response,
)


@patch("agrimarket.ingestion.nasa_power.requests.get")
def test_fetch_nasa_power_response_returns_json(mock_get):
    expected_data = {
        "properties": {
            "parameter": {
                "T2M": {
                    "20200101": 12.67,
                    "20200102": 12.75,
                }
            }
        }
    }

    mock_response = Mock()
    mock_response.json.return_value = expected_data
    mock_get.return_value = mock_response

    result = fetch_nasa_power_response(
        latitude=33.8935,
        longitude=-5.5473,
        start_date="20200101",
        end_date="20200102",
        parameters=["T2M"],
    )

    assert result == expected_data

    mock_get.assert_called_once_with(
        "https://power.larc.nasa.gov/api/temporal/daily/point",
        params={
            "parameters": "T2M",
            "community": "AG",
            "latitude": 33.8935,
            "longitude": -5.5473,
            "start": "20200101",
            "end": "20200102",
            "format": "JSON",
        },
        timeout=30,
    )


@patch("agrimarket.ingestion.nasa_power.requests.get")
def test_fetch_nasa_power_response_raises_http_error(mock_get):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = (
        requests.HTTPError("HTTP error")
    )
    mock_get.return_value = mock_response

    with pytest.raises(requests.HTTPError):
        fetch_nasa_power_response(
            latitude=33.8935,
            longitude=-5.5473,
            start_date="20200101",
            end_date="20200102",
            parameters=["T2M"],
        )



from agrimarket.ingestion.nasa_power import (
    nasa_power_response_to_dataframe,
)


def test_nasa_power_response_to_dataframe():
    data = {
        "properties": {
            "parameter": {
                "T2M": {
                    "20200101": 12.67,
                    "20200102": 12.75,
                },
                "PRECTOTCORR": {
                    "20200101": 2.5,
                    "20200102": 0.0,
                },
            }
        }
    }

    df = nasa_power_response_to_dataframe(data)

    assert list(df.columns) == [
        "date",
        "T2M",
        "PRECTOTCORR",
    ]

    assert len(df) == 2
    assert str(df["date"].dtype).startswith("datetime64")
    assert df.loc[0, "T2M"] == 12.67
    assert df.loc[0, "PRECTOTCORR"] == 2.5
    assert df.loc[1, "PRECTOTCORR"] == 0.0


def test_nasa_power_response_converts_fill_value_to_nan():
    import pandas as pd

    from agrimarket.ingestion.nasa_power import (
        nasa_power_response_to_dataframe,
    )

    data = {
        "header": {"fill_value": -999.0},
        "properties": {
            "parameter": {
                "T2M": {
                    "20200101": 15.0,
                    "20200102": -999.0,
                },
                "PRECTOTCORR": {
                    "20200101": 0.0,
                    "20200102": 2.5,
                },
            }
        },
    }

    df = nasa_power_response_to_dataframe(data)

    assert df.loc[0, "T2M"] == 15.0
    assert pd.isna(df.loc[1, "T2M"])
    assert df.loc[0, "PRECTOTCORR"] == 0.0
    assert df.loc[1, "PRECTOTCORR"] == 2.5



def test_fetch_nasa_power_for_multiple_locations():
    import pandas as pd
    import agrimarket.ingestion.nasa_power as nasa_power

    locations = [
        {"location": "Meknes", "latitude": 33.8935, "longitude": -5.5473},
        {"location": "Fes", "latitude": 34.0331, "longitude": -5.0003},
    ]

    responses = [
        {
            "properties": {
                "parameter": {
                    "T2M": {"20200101": 12.0},
                    "PRECTOTCORR": {"20200101": 0.0},
                }
            }
        },
        {
            "properties": {
                "parameter": {
                    "T2M": {"20200101": 10.0},
                    "PRECTOTCORR": {"20200101": 2.5},
                }
            }
        },
    ]

    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        nasa_power,
        "fetch_nasa_power_response",
        side_effect=responses,
    ) as mock_fetch:
        df = nasa_power.fetch_nasa_power_for_locations(
            start_date="20200101",
            end_date="20200101",
            parameters=["T2M", "PRECTOTCORR"],
            locations=locations,
        )

    assert len(df) == 2
    assert list(df["location"]) == ["Meknes", "Fes"]
    assert list(df["T2M"]) == [12.0, 10.0]
    assert list(df["PRECTOTCORR"]) == [0.0, 2.5]
    assert list(df.columns) == [
        "date", "location", "latitude", "longitude",
        "T2M", "PRECTOTCORR",
    ]
    assert isinstance(df["date"].dtype, pd.DatetimeTZDtype) is False
    assert mock_fetch.call_count == 2
