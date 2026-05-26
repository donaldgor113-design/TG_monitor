"""
Логіка пошуку ПІБ у текстах.
"""

from dataclasses import dataclass
from typing import Optional
from missing_persons.utils import normalize_text, extract_name_variations


@dataclass
class SearchResult:
    """Результат знаходження ПІБ в тексті."""
    person_name: str
    found_variation: str  # точна варіація яка була знайдена
    confidence: str  # "high", "medium", "low"
    position: int  # позиція в тексті (символи)


class MissingPersonSearchEngine:
    """
    Шукає згадки про зниклих людей у текстах.

    Приклад:
        engine = MissingPersonSearchEngine()
        results = engine.search_in_text(
            text="Карпенко Сергій виявлений...",
            person_name="Карпенко сергій миколайвич"
        )
    """

    def __init__(self):
        self.cache_variations = {}

    def search_in_text(
        self,
        text: str,
        person_name: str,
        full_variations: bool = True
    ) -> Optional[SearchResult]:
        """
        Шукає ПІБ у тексті.

        Args:
            text: текст поста/сообщения
            person_name: повне ПІБ "Карпенко сергій миколайвич"
            full_variations: використовувати всі варіації (True) або мінімум (False)

        Returns:
            SearchResult якщо знайдено, None якщо не знайдено
        """

        if not text or not person_name:
            return None

        normalized_text = normalize_text(text)

        # Отримати варіації із кешу або генерувати
        if person_name not in self.cache_variations:
            self.cache_variations[person_name] = extract_name_variations(person_name)

        variations = self.cache_variations[person_name]

        if not full_variations:
            # Використовуй тільки перші 3 варіації (найсильніші)
            variations = variations[:3]

        # Шукай по варіаціях — від найсильніших до найслабших
        for variation in variations:
            position = normalized_text.find(variation)
            if position != -1:
                confidence = self._estimate_confidence(variation, person_name)
                return SearchResult(
                    person_name=person_name,
                    found_variation=variation,
                    confidence=confidence,
                    position=position
                )

        return None

    def search_multiple_persons(
        self,
        text: str,
        persons: list[str]
    ) -> list[SearchResult]:
        """
        Шукає кількох осіб в одному тексті.

        Args:
            text: текст для пошуку
            persons: список ПІБ

        Returns:
            список знайдених результатів (може бути порожній)
        """

        results = []
        for person in persons:
            result = self.search_in_text(text, person)
            if result:
                results.append(result)

        return results

    def _estimate_confidence(self, found_var: str, original_name: str) -> str:
        """
        Оцінює впевненість у знайденому збігу.
        - high: знайдено повне ім'я або прізвище + ім'я
        - medium: знайдено прізвище + перша буква
        - low: знайдено лише прізвище
        """

        found_parts = found_var.split()
        original_parts = original_name.lower().split()

        # Повне ім'я
        if len(found_parts) >= 2:
            return "high"

        # Прізвище + перша буква
        if len(found_parts) >= 1 and "." in found_var:
            return "medium"

        # Лише прізвище
        if len(found_parts) == 1:
            return "low"

        return "low"

    def clear_cache(self):
        """Очистити кеш варіацій."""
        self.cache_variations.clear()


# Приклад використання
if __name__ == "__main__":
    engine = MissingPersonSearchEngine()

    # Test текст
    test_texts = [
        "Виявили Карпенко Сергія в Харкові. Живий, все добре.",
        "Продовжуємо пошук К. Карпенко. Будь-яка інформація чекається.",
        "Захарчук Максим, 25 років, зниклий з 10 травня. Допоможіть!",
        "Чолвиль без ісп пошукової операції",  # не має імен
    ]

    persons = [
        "Карпенко сергій миколайвич",
        "Захарчук Максим",
    ]

    for text in test_texts:
        print(f"\nТекст: {text}")
        results = engine.search_multiple_persons(text, persons)
        if results:
            for r in results:
                print(f"  ✓ Знайдено: {r.person_name} ({r.found_variation}) [{r.confidence}]")
        else:
            print("  ✗ Не знайдено")
