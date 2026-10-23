
import requests
import pandas as pd


NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)


def fetch_nasa_power_response(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    parameters: list[str],
) -> dict:
    """Retrieve daily climate data from NASA POWER."""

    request_params = {
        "parameters": ",".join(parameters),
        "community": "AG",
        "latitude": latitude,
        "longitude": longitude,
        "start": start_date,
        "end": end_date,
        "format": "JSON",
    }

    response = requests.get(
        NASA_POWER_URL,
        params=request_params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def nasa_power_response_to_dataframe(
    data: dict,
) -> pd.DataFrame:
    """Convert NASA POWER climate parameters into a daily DataFrame."""

    parameters = data["properties"]["parameter"]

    if not parameters:
        raise ValueError(
            "NASA POWER response contains no climate parameters."
        )

    frames = []

    for parameter_name, daily_values in parameters.items():
        series = pd.Series(
            daily_values,
            name=parameter_name,
            dtype="float64",
        )
        frames.append(series)

    df = pd.concat(frames, axis=1)

    # Convert NASA POWER's missing-data sentinel to NaN.
    fill_value = data.get("header", {}).get("fill_value", -999.0)
    df = df.replace(fill_value, float("nan"))

    df.index = pd.to_datetime(
        df.index,
        format="%Y%m%d",
        errors="raise",
    )

    df.index.name = "date"

    return df.reset_index()



MOROCCO_LOCATIONS = [
    {"location": "Meknes", "latitude": 33.8935, "longitude": -5.5473},
    {"location": "Fes", "latitude": 34.0331, "longitude": -5.0003},
    {"location": "Beni Mellal", "latitude": 32.3373, "longitude": -6.3498},
    {"location": "Marrakech", "latitude": 31.6295, "longitude": -7.9811},
    {"location": "Agadir", "latitude": 30.4278, "longitude": -9.5981},
    {"location": "Kenitra", "latitude": 34.2610, "longitude": -6.5802},
    {"location": "Rabat", "latitude": 34.0209, "longitude": -6.8416},
    {"location": "Casablanca", "latitude": 33.5731, "longitude": -7.5898},
    {"location": "Larache", "latitude": 35.1932, "longitude": -6.1557},
    {"location": "Sidi Kacem", "latitude": 34.2215, "longitude": -5.7077},
    {"location": "Sidi Slimane", "latitude": 34.2648, "longitude": -5.9250},
    {"location": "El Jadida", "latitude": 33.2316, "longitude": -8.5007},
    {"location": "Safi", "latitude": 32.2994, "longitude": -9.2372},
    {"location": "Tangier", "latitude": 35.7595, "longitude": -5.8340},
    {"location": "Tetouan", "latitude": 35.5889, "longitude": -5.3626},
    {"location": "Chefchaouen", "latitude": 35.1688, "longitude": -5.2636},
    {"location": "Taounate", "latitude": 34.5366, "longitude": -4.6401},
    {"location": "Taza", "latitude": 34.2133, "longitude": -4.0103},
    {"location": "Oujda", "latitude": 34.6814, "longitude": -1.9086},
    {"location": "Settat", "latitude": 33.0010, "longitude": -7.6166},
    {"location": "Khenifra", "latitude": 32.9391, "longitude": -5.6675},
    {"location": "Essaouira", "latitude": 31.5085, "longitude": -9.7595},
    {"location": "Taroudant", "latitude": 30.4703, "longitude": -8.8769},
    {"location": "Tiznit", "latitude": 29.6974, "longitude": -9.7316},
    {"location": "Guelmim", "latitude": 28.9870, "longitude": -10.0574},
    {"location": "Ouarzazate", "latitude": 30.9335, "longitude": -6.9370},
    {"location": "Errachidia", "latitude": 31.9314, "longitude": -4.4266},
    {"location": "Zagora", "latitude": 30.3324, "longitude": -5.8384},
    {"location": "Laayoune", "latitude": 27.1536, "longitude": -13.2033},
    {"location": "Dakhla", "latitude": 23.6848, "longitude": -15.9570},
]


def fetch_nasa_power_for_locations(
    start_date: str,
    end_date: str,
    parameters: list[str],
    locations: list[dict] | None = None,
) -> pd.DataFrame:
    """Fetch and combine daily NASA POWER data for multiple locations."""

    selected_locations = (
        MOROCCO_LOCATIONS if locations is None else locations
    )

    if not selected_locations:
        raise ValueError("At least one location must be provided.")

    frames = []

    for location_info in selected_locations:
        data = fetch_nasa_power_response(
            latitude=location_info["latitude"],
            longitude=location_info["longitude"],
            start_date=start_date,
            end_date=end_date,
            parameters=parameters,
        )

        df = nasa_power_response_to_dataframe(data)
        df["location"] = location_info["location"]
        df["latitude"] = location_info["latitude"]
        df["longitude"] = location_info["longitude"]
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    column_order = [
        "date",
        "location",
        "latitude",
        "longitude",
        *parameters,
    ]

    return combined[column_order]
