"""
Утиліти для пошуку зниклих осіб: нормалізація ПІБ, приведення тексту.
"""

import re
import unidecode


def normalize_text(text: str) -> str:
    """
    Нормалізує текст для пошуку:
    - нижний регістр
    - видаляє зайві пробіли
    - замінює деякі символи
    """
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('ё', 'е')  # якщо буде російський текст
    return text


def transliterate_latin_to_cyrillic(text: str) -> str:
    """
    Конвертує латиницю в кирилицю для імен.
    Приклад: Petrenco → Петренко
    """
    # Спеціальні випадки для українських/російських імен
    replacements = {
        'a': 'а', 'b': 'б', 'c': 'ц', 'd': 'д', 'e': 'е',
        'f': 'ф', 'g': 'г', 'h': 'х', 'i': 'і', 'j': 'й',
        'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о',
        'p': 'п', 'q': 'к', 'r': 'р', 's': 'с', 't': 'т',
        'u': 'у', 'v': 'в', 'w': 'в', 'x': 'кс', 'y': 'й',
        'z': 'з'
    }

    result = []
    text = text.lower()
    i = 0
    while i < len(text):
        char = text[i]
        if char in replacements:
            result.append(replacements[char])
        else:
            result.append(char)
        i += 1

    return ''.join(result)


def extract_name_variations(full_name: str) -> list[str]:
    """
    Генерує варіації ПІБ для пошуку.

    Вхід: "Карпенко сергій миколайвич"
    Вихід: [
        "карпенко сергій миколайвич",
        "карпенко сергій",
        "карпенко с.",
        "с. карпенко",
        "карпенко с м",
        ...
    ]
    """
    variations = set()
    full_name = normalize_text(full_name)

    # Базовий варіант
    variations.add(full_name)

    parts = full_name.split()

    if len(parts) >= 2:
        # Прізвище + Ім'я
        variations.add(f"{parts[0]} {parts[1]}")

        # Прізвище + перша буква Імені
        variations.add(f"{parts[0]} {parts[1][0]}.")

        # Перша буква Імені + Прізвище
        variations.add(f"{parts[1][0]}. {parts[0]}")

    if len(parts) >= 3:
        # Прізвище + Ім'я + Прізвище
        variations.add(f"{parts[0]} {parts[1]} {parts[2]}")

        # Прізвище + Ім'я + По батькові (першої букви)
        variations.add(f"{parts[0]} {parts[1]} {parts[2][0]}.")

        # З дефісами
        variations.add(f"{parts[0]}-{parts[1]}")

        # Скорочено: прізвище + 2-3 букви імені
        variations.add(f"{parts[0]} {parts[1][:2]}")

    # Варіант лише з прізвищем (обережно — може бути помилка)
    if parts:
        variations.add(parts[0])

    # Додати транслітеровані варіанти (латиниця → кирилиця)
    latin_version = transliterate_latin_to_cyrillic(full_name)
    if latin_version != full_name:
        for var in list(variations):
            latin_var = transliterate_latin_to_cyrillic(var)
            variations.add(latin_var)

    return sorted(list(variations))


def escape_html(text: str) -> str:
    """Екранує HTML для безпечного запису в таблиці."""
    if not text:
        return ""
    return (text.replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;")
               .replace('"', "&quot;")
               .replace("'", "&#39;"))


def extract_text_from_message(message) -> str:
    """
    Витягує текст з Telethon Message об'єкту.
    Враховує: текст, підписи до медіа.
    """
    text_parts = []

    # Основний текст
    if hasattr(message, 'text') and message.text:
        text_parts.append(message.text)

    # Підпис до фото/відео/документа
    if hasattr(message, 'caption') and message.caption:
        text_parts.append(message.caption)

    return " ".join(text_parts)


# Test варіанти ПІБ для розробки
SAMPLE_PERSONS = [
    "Карпенко сергій миколайвич",
    "Захарчук Максим",
    "Цюпенко Андрій Володимирович"
]

if __name__ == "__main__":
    for person in SAMPLE_PERSONS:
        variations = extract_name_variations(person)
        print(f"\n{person}:")
        for var in variations:
            print(f"  - {var}")
