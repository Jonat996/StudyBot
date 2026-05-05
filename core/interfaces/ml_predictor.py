from abc import ABC, abstractmethod
from core.entities.task import Task


class MLPredictor(ABC):
    @abstractmethod
    def predict_time(self, task: Task) -> float:
        """Predicts real study time in hours for a given task."""

    @abstractmethod
    def predict_compliance(self, task: Task) -> dict:
        """Returns {'will_complete': bool, 'probability': float}."""

    @abstractmethod
    def classify_priority(self, task: Task) -> str:
        """Returns priority level: 'Maxima' | 'Alta' | 'Media' | 'Baja'."""
