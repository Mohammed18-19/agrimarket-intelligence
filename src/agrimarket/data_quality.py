import pandas as pd

def validate_required_columns(
        df: pd.DataFrame,
        required_columns: list[str],
) -> None:
    """Check that all required columns exist in a Dataframe."""

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )



def validate_no_missing_values(df: pd.DataFrame) -> None:
    """Check that the DataFrame contains no missing values."""

    if df.isnull().values.any():
        raise ValueError("DataFrame contains missing values")



def validate_no_duplicate_rows(df: pd.DataFrame) -> None:
    """Check that the DataFrame contains no duplicate rows."""

    if df.duplicated().any():
        raise ValueError("DataFrame contains duplicate rows")


def validate_numeric_columns(
        df: pd.DataFrame,
        numeric_columns: list[str]
) -> None:
    """Check that required numeric columns contain numeric values."""

    for column in numeric_columns:
        if column not in df.columns:
            raise ValueError(f"Missing required column: {column}")

        if not pd.api.types.is_numeric_dtype(df[column]):
            raise ValueError(
                f"Column {column} must contain numeric data"
            )



def validate_minimum_value(
    df: pd.DataFrame,
    column: str,
    minimum: float,
) -> None:
    """Check that all values in a column meet a minimum threshold."""

    if column not in df.columns:
        raise ValueError(f"Missing required column: {column}")

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(
            f"Column '{column}' must contain numeric data"
        )

    if (df[column] < minimum).any():
        raise ValueError(
            f"Column '{column}' contains values below {minimum}"
        )


def validate_dataset(
    df: pd.DataFrame,
    required_columns: list[str],
    numeric_columns: list[str],
    minimum_values: dict[str, float],
) -> None:
    """Run all configured data-quality checks."""

    validate_required_columns(df, required_columns)
    validate_no_missing_values(df)
    validate_no_duplicate_rows(df)
    validate_numeric_columns(df, numeric_columns)

    for column, minimum in minimum_values.items():
        validate_minimum_value(df, column, minimum)