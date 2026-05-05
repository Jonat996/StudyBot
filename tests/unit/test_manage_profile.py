import pytest
from unittest.mock import MagicMock
from core.entities.student import Student
from core.use_cases.manage_profile import ManageProfile


def make_student(phone="+573001234567", name="Ana", profile=None):
    return Student(
        id="student-uuid-001",
        name=name,
        phone=phone,
        profile=profile or {},
    )


def make_repo(existing_student=None):
    repo = MagicMock()
    repo.find_by_phone.return_value = existing_student
    repo.find_by_id.return_value = existing_student
    repo.create.return_value = make_student()
    repo.update_profile.return_value = True
    return repo


class TestGetOrCreateStudent:
    def test_returns_existing_student(self):
        student = make_student()
        repo = make_repo(existing_student=student)
        use_case = ManageProfile(repo)

        result = use_case.get_or_create_student(phone=student.phone, channel="whatsapp")

        repo.create.assert_not_called()
        assert result.id == student.id

    def test_creates_new_student_when_not_found(self):
        repo = make_repo(existing_student=None)
        use_case = ManageProfile(repo)

        use_case.get_or_create_student(phone="+573009999999", channel="whatsapp")

        repo.create.assert_called_once()

    def test_update_profile_delegates_to_repo(self):
        student = make_student()
        repo = make_repo(existing_student=student)
        use_case = ManageProfile(repo)

        result = use_case.update_profile(student.id, {"compliance_rate": 0.9})

        repo.update_profile.assert_called_once_with(student.id, {"compliance_rate": 0.9})
        assert result is True


class TestGetContextForLLM:
    def test_returns_formatted_profile(self):
        profile = {"difficult_subjects": ["Calculo"], "compliance_rate": 0.8}
        student = make_student(name="Carlos", profile=profile)
        repo = make_repo(existing_student=student)
        use_case = ManageProfile(repo)

        context = use_case.get_context_for_llm(student.id)

        assert "Carlos" in context
        assert "Calculo" in context

    def test_returns_no_profile_message_when_not_found(self):
        repo = make_repo(existing_student=None)
        use_case = ManageProfile(repo)

        context = use_case.get_context_for_llm("nonexistent-id")

        assert "Sin perfil" in context
