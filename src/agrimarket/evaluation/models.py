"""The models that the evaluation scripts compare. Edit them by hand.

Each class forecasts ONE time series and has the same three methods:

    fit(train_data)    train_data is a DataFrame with columns ``timestamp``
                       and ``target`` for a single entity, oldest first.
                       Calling fit again must replace the previous fit.
    predict(horizon)   Return ``horizon`` future values, one step apart,
                       starting right after the last training timestamp.
    get_params()       Return the hyperparameters as a plain dict. These are
                       logged to MLflow, so keep them in sync with the code.

``describe()`` returns a one-line description of the architecture for MLflow.

The evaluation engine fits and scores one entity (for example one crop) at a
time, so a model never sees another entity's data.

To try something new, change the body of ``fit``/``predict`` and the values
in ``get_params``/``describe``, then run the matching ``scripts/evaluate_*``
script. MLflow stores the class source of every run, so older versions stay
recoverable. If you add a trainable model that tracks genuine training and
validation losses, expose them as ``self.loss_history``, a dict such as
``{"train_loss": [...], "val_loss": [...]}``. They are logged only when that
attribute exists. Because the evaluation refits the model for every entity
and window, the logged curves are those of the last fit.
"""

import numpy as np
import pandas as pd

from agrimarket.analytics.forecasting import forecast_production


class YearlyModel:
    """Annual crop production, one crop at a time.

    Uses the project's existing baselines in
    ``agrimarket.analytics.forecasting.forecast_production``:

    - ``"naive"``: repeat the last observed value.
    - ``"linear_trend"``: straight-line fit over the whole training window.

    To replace the algorithm (for example with scikit-learn's
    ``LinearRegression`` or another estimator), rewrite ``fit`` and
    ``predict`` here.
    """

    def __init__(self, method: str = "naive"):
        self.method = method
        self._series = None
        self._last_year = None

    def fit(self, train_data):
        self._last_year = int(train_data["timestamp"].dt.year.iloc[-1])
        self._series = {
            "Item": ["series"] * len(train_data),
            "Year": train_data["timestamp"].dt.year.to_numpy(),
            "Unit": ["t"] * len(train_data),
            "Value": train_data["target"].to_numpy(dtype=float),
        }
        return self

    def predict(self, horizon: int) -> np.ndarray:
        frame = pd.DataFrame(self._series)
        return np.array([
            forecast_production(
                frame, "series", self._last_year + step, self.method
            )["predicted_production"]
            for step in range(1, horizon + 1)
        ])

    def get_params(self) -> dict:
        return {"method": self.method}

    def describe(self) -> str:
        return {
            "naive": "Last observed value (existing baseline)",
            "linear_trend": "Linear trend over all training years (existing baseline)",
        }.get(self.method, f"forecast_production(method={self.method!r})")


class YearlyPriceModel:
    """Annual producer price of one crop, one crop at a time.

    Separate from ``YearlyModel`` because the target is a price, not a
    production quantity. Two standard baselines:

    - ``"naive"``: repeat the last observed price.
    - ``"drift"``: continue the average yearly change, that is the straight
      line through the first and the last training price.

    Prices are never converted or combined across crops. To try another
    algorithm, rewrite ``fit`` and ``predict`` here.
    """

    METHODS = ("naive", "drift")

    def __init__(self, method: str = "naive"):
        if method not in self.METHODS:
            raise ValueError(f"method must be one of {self.METHODS}")
        self.method = method
        self._last = None
        self._step = 0.0

    def fit(self, train_data):
        values = train_data["target"].to_numpy(dtype=float)
        self._last = float(values[-1])
        # Average change per period. Zero for naive and for a single point.
        self._step = (
            (values[-1] - values[0]) / (len(values) - 1)
            if self.method == "drift" and len(values) > 1
            else 0.0
        )
        return self

    def predict(self, horizon: int) -> np.ndarray:
        return self._last + self._step * np.arange(1, horizon + 1)

    def get_params(self) -> dict:
        return {"method": self.method}

    def describe(self) -> str:
        return {
            "naive": "Last observed annual price",
            "drift": "Last annual price plus the average yearly change over the training years",
        }[self.method]