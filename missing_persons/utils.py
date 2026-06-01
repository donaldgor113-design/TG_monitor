import re
import logging
from typing import List, Set, Dict, Tuple
from dataclasses import dataclass

try:
    import pymorphy2
    morph = pymorphy2.MorphAnalyzer(lang='uk')
    MORPH_AVAILABLE = True
except:
    MORPH_AVAILABLE = False

logger = logging.getLogger(__name__)

CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
    'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}

LATIN_TO_CYRILLIC = {v: k for k, v in CYRILLIC_TO_LATIN.items()}
LATIN_TO_CYRILLIC.update({
    'a': 'а', 'b': 'б', 'c': 'ц', 'd': 'д', 'e': 'е', 'f': 'ф',
    'g': 'г', 'h': 'х', 'i': 'і', 'j': 'й', 'k': 'к', 'l': 'л',
    'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р',
    's': 'с', 't': 'т', 'u': 'у', 'v': 'в', 'w': 'в', 'x': 'х',
    'y': 'и', 'z': 'з'
})


@dataclass
class PersonData:
    surname: str
    name: str
    patronymic: str
    birth_date: str = ""
    missing_from_date: str = ""
    status: str = "missing"

    def get_full_name(self) -> str:
        parts = [self.surname, self.name]
        if self.patronymic:
            parts.append(self.patronymic)
        return " ".join(filter(None, parts))

    def is_publication_relevant(self, pub_date: str) -> bool:
        """Перевіряє, чи публікація релевантна (після дати коли людина зникла)."""
        if not self.missing_from_date:
            return True  # Якщо дата не встановлена, всі публікації релевантні

        try:
            from datetime import datetime
            # Конвертуємо дати в формат YYYY-MM-DD якщо потребується
            pub = self._parse_date(pub_date)
            missing = self._parse_date(self.missing_from_date)

            if pub and missing:
                return pub >= missing
        except:
            pass

        return True  # При помилці вважаємо релевантною

    @staticmethod
    def _parse_date(date_str: str):
        """Парсить дату різних форматів (DD.MM.YYYY, YYYY-MM-DD)."""
        if not date_str:
            return None

        try:
            from datetime import datetime
            # Спробуємо DD.MM.YYYY
            if "." in date_str:
                return datetime.strptime(date_str.strip(), "%d.%m.%Y")
            # Спробуємо YYYY-MM-DD
            elif "-" in date_str:
                return datetime.strptime(date_str.strip(), "%Y-%m-%d")
        except:
            pass

        return None


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('-', ' ')
    return text


def get_word_root(word: str) -> str:
    """Отримати корінь слова для більш гнучкого пошуку."""
    if not word or len(word) < 3:
        return word.lower()

    word_lower = word.lower().strip()

    if MORPH_AVAILABLE:
        try:
            parsed = morph.parse(word_lower)
            if parsed and parsed[0].normal_form:
                normal = parsed[0].normal_form.lower()
                if len(normal) >= 3:
                    return normal
        except:
            pass

    # Навіть без морфаналізу повертаємо слово як є
    return word_lower


def get_word_forms(word: str) -> Set[str]:
    """Отримати можливі варіанти слова для пошуку."""
    if not word or len(word) < 2:
        return {word.lower()}

    forms = set()
    word = word.lower().strip()
    forms.add(word)

    # Додаємо корінь слова
    root = get_word_root(word)
    if root and len(root) >= 3:
        forms.add(root)

    # Для коротких слів (імена) додаємо перші 3+ символи
    if len(word) >= 4:
        forms.add(word[:len(word)-1])  # без останньої букви (может быть закінченням)
        if len(word) >= 5:
            forms.add(word[:len(word)-2])  # без останніх двох букв

    return forms


def search_person_in_text(text: str, person: PersonData) -> Tuple[bool, str]:
    """
    Шукає особу в тексті з урахуванням морфології та різних форм ПІБ.
    Повертає (знайдена, деталь_збігу).
    """
    text_lower = normalize_text(text)
    words = text_lower.split()

    if not person.surname:
        return False, ""

    surname_forms = get_word_forms(person.surname)
    name_forms = get_word_forms(person.name) if person.name else set()
    patronymic_forms = get_word_forms(person.patronymic) if person.patronymic else set()

    found_surname_word = None
    found_name_word = None
    found_patronymic_word = None
    found_surname = None
    found_name = None
    found_patronymic = None

    for word in words:
        # Шукаємо прізвище
        if found_surname is None:
            for form in surname_forms:
                if form and len(form) >= 3 and form in word:
                    found_surname = person.surname
                    found_surname_word = word
                    break

        # Шукаємо ім'я
        if found_name is None and name_forms:
            for form in name_forms:
                if form and len(form) >= 3 and form in word:
                    found_name = person.name
                    found_name_word = word
                    break

        # Шукаємо по-батькові
        if found_patronymic is None and patronymic_forms:
            for form in patronymic_forms:
                if form and len(form) >= 3 and form in word:
                    found_patronymic = person.patronymic
                    found_patronymic_word = word
                    break

    # Формуємо результат
    if found_surname and found_name:
        if found_patronymic:
            match_detail = f"{found_surname} {found_name} {found_patronymic}"
            return True, match_detail
        else:
            match_detail = f"{found_surname} {found_name}"
            return True, match_detail

    # Якщо знайдено прізвище та по-батькові (але не ім'я), це також добре
    if found_surname and found_patronymic and person.name:
        match_detail = f"{found_surname} (по-батькові {found_patronymic})"
        return True, match_detail

    # Якщо знайдено тільки прізвище - це недостатньо точно
    # (щоб уникнути помилкових результатів як у нас було)
    if found_surname and not found_name and not found_patronymic:
        return False, ""

    return False, ""


def latin_to_cyrillic(text: str) -> str:
    result = []
    i = 0
    text = text.lower()
    while i < len(text):
        if i + 1 < len(text) and text[i:i+2] in LATIN_TO_CYRILLIC:
            result.append(LATIN_TO_CYRILLIC[text[i:i+2]])
            i += 2
        elif text[i] in LATIN_TO_CYRILLIC:
            result.append(LATIN_TO_CYRILLIC[text[i]])
            i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def generate_name_variations(full_name: str) -> Set[str]:
    normalized = normalize_text(full_name)
    parts = normalized.split()

    if not parts:
        return set()

    variations = set()
    variations.add(normalized)

    if len(parts) >= 2:
        surname, name = parts[0], parts[1]
        variations.add(f"{surname} {name[0]}.")
        variations.add(f"{surname} {name[0]}")
        variations.add(f"{name[0]}. {surname}")
        variations.add(f"{name[0]} {surname}")

        if len(parts) >= 3:
            patronymic = parts[2]
            full_form = f"{surname} {name} {patronymic}"
            variations.add(full_form)
            variations.add(f"{surname} {name[0]}. {patronymic[0]}.")

    try:
        latin_form = latin_to_cyrillic(full_name)
        variations.add(normalize_text(latin_form))
    except:
        pass

    return variations


def search_name_in_text(text: str, full_name: str) -> bool:
    normalized_text = normalize_text(text)
    variations = generate_name_variations(full_name)

    for variation in variations:
        if variation in normalized_text:
            return True

    return False


def escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
