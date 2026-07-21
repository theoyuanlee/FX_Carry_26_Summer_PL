from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class ExpandingPrediction:
    probability: pd.Series
    coefficients: pd.DataFrame


def expanding_logistic_predictions(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    target_column: str = "target_next_positive",
    minimum_training_months: int = 60,
    random_state: int = 42,
) -> ExpandingPrediction:
    """Generate strictly expanding-window one-step-ahead probabilities."""
    probabilities = pd.Series(index=dataset.index, dtype=float, name="probability")
    coefficient_rows: list[pd.Series] = []

    for i in range(minimum_training_months, len(dataset)):
        train = dataset.iloc[:i].dropna(subset=[target_column])
        x_train = train[feature_columns]
        y_train = train[target_column].astype(int)

        if y_train.nunique() < 2:
            continue

        model = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        penalty="l2",
                        C=1.0,
                        max_iter=2000,
                        random_state=random_state,
                    ),
                ),
            ]
        )

        model.fit(x_train, y_train)
        x_test = dataset.iloc[[i]][feature_columns]
        probabilities.iloc[i] = model.predict_proba(x_test)[0, 1]

        coefficients = model.named_steps["model"].coef_[0]
        coefficient_rows.append(
            pd.Series(coefficients, index=feature_columns, name=dataset.index[i])
        )

    return ExpandingPrediction(
        probability=probabilities,
        coefficients=pd.DataFrame(coefficient_rows),
    )


def probability_exposure(
    probability: pd.Series,
    lower: float = 0.40,
    upper: float = 0.60,
) -> pd.Series:
    """Map a probability forecast into a continuous exposure between zero and one."""
    if upper <= lower:
        raise ValueError("upper must be greater than lower")
    return ((probability - lower) / (upper - lower)).clip(0.0, 1.0)
