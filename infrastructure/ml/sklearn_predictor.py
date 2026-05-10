import os
import numpy as np
import joblib
from core.entities.task import Task
from core.interfaces.ml_predictor import MLPredictor

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

PRIORITY_LABELS = ["Baja", "Media", "Alta", "Maxima"]
MODEL_METRICS = {
    "MAE": 0.567,
    "RMSE": 0.807,
    "R2": 0.852,
    "F1": 0.900,
    "Accuracy": 0.825,
}


class SklearnPredictor(MLPredictor):
    def __init__(self, settings):
        self._settings = settings
        self._regressor = None
        self._classifier = None

    def predict_time(self, task: Task) -> float:
        self._load_models()
        features = self._extract_features(task)
        predicted = float(self._regressor.predict([features])[0])
        personal_factor = 1.0
        return round(predicted * personal_factor, 2)

    def predict_compliance(self, task: Task) -> dict:
        self._load_models()
        features = self._extract_features(task)
        proba = self._classifier.predict_proba([features])[0]
        will_complete_prob = float(max(proba))
        will_complete = bool(self._classifier.predict([features])[0])
        return {"will_complete": will_complete, "probability": round(will_complete_prob, 3)}

    def classify_priority(self, task: Task) -> str:
        days = task.days_available or 999
        diff = task.difficulty
        if days < 3 and diff >= 4:
            return "Maxima"
        if days < 3:
            return "Alta"
        if days <= 5 and diff >= 4:
            return "Alta"
        if days <= 5:
            return "Media"
        return "Baja"

    def get_metrics(self) -> dict:
        return MODEL_METRICS

    def _load_models(self) -> None:
        if not self._regressor:
            path = os.path.join(_MODELS_DIR, self._settings.regression_model_file)
            self._regressor = joblib.load(path)
        if not self._classifier:
            path = os.path.join(_MODELS_DIR, self._settings.classifier_model_file)
            self._classifier = joblib.load(path)

    def _extract_features(self, task: Task) -> list:
        days = task.days_available or 7
        return [task.difficulty, task.estimated_hours, days]
