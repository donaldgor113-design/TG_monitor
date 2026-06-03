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

# По-батькові завжди містять ці суфікси: -ович/-овна та їх варіанти
PATRONYMIC_RE = re.compile(r'^.{3,}(ович|евич|євич|овна|евна|євна|івна|ївна)', re.IGNORECASE)

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


def is_patronymic_form(word: str) -> bool:
    """Визначає, чи слово є по-батькові (містить суфікс -ович/-овна тощо)."""
    return len(word) > 6 and bool(PATRONYMIC_RE.match(word.lower()))


def get_lemma(word: str) -> str:
    """Повертає нормальну (словникову) форму слова через pymorphy2."""
    if not word:
        return ""
    w = word.lower().strip()
    if MORPH_AVAILABLE:
        try:
            parsed = morph.parse(w)
            if parsed and parsed[0].normal_form:
                return parsed[0].normal_form.lower()
        except:
            pass
    return w


def search_person_in_text(text: str, person: PersonData) -> Tuple[bool, str]:
    """
    Шукає особу в тексті через порівняння лем (нормальних форм слів).
    Вимагає: ПРІЗВИЩЕ + ІМ'Я одночасно в межах 3 слів.
    Слова-по-батькові (-ович/-овна) ніколи не матчаться з прізвищем чи ім'ям.
    """
    if not person.surname or not person.name:
        return False, ""

    text_lower = normalize_text(text)
    words = text_lower.split()

    surname_lemma = get_lemma(person.surname)
    name_lemma = get_lemma(person.name)
    patronymic_lemma = get_lemma(person.patronymic) if person.patronymic else None

    found_surname_idx = None
    found_name_idx = None
    found_patronymic_idx = None

    for idx, word in enumerate(words):
        word_lemma = get_lemma(word)
        word_is_patronymic = is_patronymic_form(word)

        # Прізвище: слово НЕ є по-батькові + лема збігається
        if found_surname_idx is None and not word_is_patronymic:
            if word_lemma == surname_lemma:
                found_surname_idx = idx

        # Ім'я: слово НЕ є по-батькові + лема збігається
        if found_name_idx is None and not word_is_patronymic:
            if word_lemma == name_lemma:
                found_name_idx = idx

        # По-батькові: слово є по-батькові формою + лема збігається
        if found_patronymic_idx is None and patronymic_lemma and word_is_patronymic:
            if word_lemma == patronymic_lemma:
                found_patronymic_idx = idx

    # Мінімум: прізвище + ім'я в межах 3 слів
    if found_surname_idx is not None and found_name_idx is not None:
        if abs(found_surname_idx - found_name_idx) <= 3:
            if found_patronymic_idx is not None:
                return True, f"{person.surname} {person.name} {person.patronymic}"
            return True, f"{person.surname} {person.name}"

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
