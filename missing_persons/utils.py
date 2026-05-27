import re
from typing import List, Set

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


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('-', ' ')
    return text


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
