import re
import logging
from typing import List, Set, Dict, Tuple, Optional
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


def get_all_forms(word: str) -> Set[str]:
    """Генерує всі граматичні форми слова (всі відмінки) через pymorphy2."""
    forms = {word.lower()}
    if not word or len(word) < 2:
        return forms
    if MORPH_AVAILABLE:
        try:
            parsed = morph.parse(word.lower())
            if parsed:
                for form in parsed[0].lexeme:
                    f = form.word.lower()
                    if f:
                        forms.add(f)
        except:
            pass
    return forms


def extract_birth_date(text: str) -> Optional[str]:
    """
    Витягує дату народження з тексту (маркер р.н.).
    Повертає рядок DD.MM.YYYY або None.
    """
    # Дата перед р.н.: "15.08.1970р.н", "12.07.1986.р.н.", "03.09.1977 р.н."
    m = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})[.\s]*р\.?\s*н', text, re.IGNORECASE)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2010:
                return f"{d:02d}.{mo:02d}.{y}"
        except:
            pass
    # р.н. перед датою: "р.н. 15.08.1970"
    m = re.search(r'р\.?\s*н\.?\s*(\d{1,2})[./](\d{1,2})[./](\d{4})', text, re.IGNORECASE)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2010:
                return f"{d:02d}.{mo:02d}.{y}"
        except:
            pass
    return None


def _norm_date(date_str: str) -> str:
    """Нормалізує дату до формату DD.MM.YYYY."""
    if not date_str:
        return ""
    m = re.match(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', date_str.strip())
    if m:
        return f"{int(m.group(1)):02d}.{int(m.group(2)):02d}.{m.group(3)}"
    return date_str.strip()


def search_person_in_text(text: str, person: PersonData) -> Tuple[bool, str]:
    """
    Шукає особу в тексті по всіх відмінках прізвища, імені, по-батькові.
    Вимагає: ПРІЗВИЩЕ + ІМ'Я в межах 4 слів (точне співпадіння форм).
    Якщо в тексті є дата р.н. І у особи є дата нар. в базі — вони ОБОВ'ЯЗКОВО мають збігатись.
    """
    if not person.surname or not person.name:
        return False, ""

    text_lower = normalize_text(text)
    words = text_lower.split()

    surname_forms = get_all_forms(person.surname)
    name_forms = get_all_forms(person.name)
    patronymic_forms = get_all_forms(person.patronymic) if person.patronymic else set()

    found_surname_idx = None
    found_name_idx = None
    found_patronymic_idx = None

    for idx, word in enumerate(words):
        if found_surname_idx is None and word in surname_forms:
            found_surname_idx = idx
        if found_name_idx is None and word in name_forms:
            found_name_idx = idx
        if found_patronymic_idx is None and patronymic_forms and word in patronymic_forms:
            found_patronymic_idx = idx

    if found_surname_idx is None or found_name_idx is None:
        return False, ""

    if abs(found_surname_idx - found_name_idx) > 4:
        return False, ""

    # Перевірка дати народження: якщо в тексті є р.н. І в базі є дата — мають збігатись
    if person.birth_date:
        text_birth_date = extract_birth_date(text)
        if text_birth_date is not None:
            if _norm_date(text_birth_date) != _norm_date(person.birth_date):
                return False, ""

    if found_patronymic_idx is not None and abs(found_surname_idx - found_patronymic_idx) <= 4:
        return True, f"{person.surname} {person.name} {person.patronymic}"
    return True, f"{person.surname} {person.name}"


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
