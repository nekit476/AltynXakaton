"""Общая иерархия ошибок core/errors.py — контракт между domain и web."""

import uuid

import allure
import pytest

from core.errors import AppError, NotFound


@allure.feature("Платформа")
@allure.story("Ошибки")
class TestNotFound:
    """NotFound — «нет или чужой».

    Тесты:
      1. NotFound перехватывается общим except AppError и несёт контекст в атрибутах
    """

    @allure.title("NotFound ловится как AppError и хранит сущность и id")
    def test_not_found_is_app_error_with_context(self):
        request_id = uuid.uuid4()

        with pytest.raises(AppError, match="не найден") as caught:
            raise NotFound("Заявка", request_id)

        assert isinstance(caught.value, NotFound)
        assert caught.value.entity == "Заявка"
        assert caught.value.entity_id == request_id
