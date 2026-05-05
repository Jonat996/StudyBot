import pytest
from datetime import date
from unittest.mock import MagicMock
from core.entities.task import Task
from core.use_cases.generate_plan import GeneratePlan


def make_predictor(predicted_hours=2.0, compliance_prob=0.85):
    predictor = MagicMock()
    predictor.predict_time.return_value = predicted_hours
    predictor.predict_compliance.return_value = {
        "will_complete": compliance_prob >= 0.5,
        "probability": compliance_prob,
    }
    return predictor


def make_task(subject="Calculo", difficulty=3, estimated_hours=2.0, days_available=5):
    return Task(
        subject=subject,
        difficulty=difficulty,
        estimated_hours=estimated_hours,
        due_date=date.today(),
        days_available=days_available,
    )


class TestPriorityRules:
    def test_maxima_when_urgent_and_hard(self):
        task = make_task(difficulty=4, days_available=2)
        use_case = GeneratePlan(make_predictor())
        enriched, _ = use_case.execute([task])
        assert enriched[0].priority == "Maxima"

    def test_alta_when_urgent_easy(self):
        task = make_task(difficulty=2, days_available=2)
        use_case = GeneratePlan(make_predictor())
        enriched, _ = use_case.execute([task])
        assert enriched[0].priority == "Alta"

    def test_alta_when_mid_term_hard(self):
        task = make_task(difficulty=4, days_available=4)
        use_case = GeneratePlan(make_predictor())
        enriched, _ = use_case.execute([task])
        assert enriched[0].priority == "Alta"

    def test_media_when_mid_term_easy(self):
        task = make_task(difficulty=2, days_available=4)
        use_case = GeneratePlan(make_predictor())
        enriched, _ = use_case.execute([task])
        assert enriched[0].priority == "Media"

    def test_baja_when_plenty_of_time(self):
        task = make_task(difficulty=2, days_available=10)
        use_case = GeneratePlan(make_predictor())
        enriched, _ = use_case.execute([task])
        assert enriched[0].priority == "Baja"


class TestScheduleGeneration:
    def test_schedule_has_all_days(self):
        task = make_task()
        use_case = GeneratePlan(make_predictor())
        _, schedule = use_case.execute([task])
        assert "monday" in schedule.slots_by_day
        assert "saturday" in schedule.slots_by_day

    def test_max_load_pct_within_bounds(self):
        tasks = [make_task(subject=f"Materia {i}", days_available=3) for i in range(4)]
        use_case = GeneratePlan(make_predictor(predicted_hours=1.5))
        _, schedule = use_case.execute(tasks)
        assert schedule.max_day_load_pct <= 100.0

    def test_compliance_probability_is_set(self):
        task = make_task()
        use_case = GeneratePlan(make_predictor(compliance_prob=0.75))
        enriched, _ = use_case.execute([task])
        assert enriched[0].compliance_probability == 0.75
