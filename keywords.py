# keywords.py
import re

CLASSIFIER_MODES = {
    "legacy": "Legacy",
    "shadow": "Shadow",
    "v2": "V2",
}

KEYWORD_FORMS = {
    "поліція": [
        "поліція", "поліції", "поліцією",
        "поліцейський", "поліцейського", "поліцейському",
        "поліцейська", "поліцейські", "поліцейських", "мвс",
        "патрульна поліція", "правоохоронці", "правоохоронець",
        "слідчий", "слідчі", "оперуповноважений", "наряд поліції",
        "екіпаж поліції", "поліцейський патруль"
    ],
    "тцк": [
        "тцк", "тцк сп", "тцк та сп",
        "військомат", "військкомат", "військомату",
        "повістка", "повістки", "повістку", "резерв+",
        "мобілізаційне розпорядження", "вручення повістки",
        "вручили повістку", "військовий облік", "оповіщення військовозобов'язаних",
    ],
    "підпал": [
        "підпал", "підпали", "пожежники",
        "дснс", "рятівники", "мнс", "пошкодження майна",
        "загоряння", "коктейль молотова", "пожежа",
        "підпалили", "умисний підпал", "підпал авто",
        "підпал будинку", "підпалили автомобіль", "займання"
    ],
    "зброя": [
        "зброя", "холодна зброя", "пістолет", "автомат", "граната",
        "ніж", "вибухівка", "кастет", "вибуховий пристрій",
        "предмет схожий на зброю", "заточка",
        "боєприпаси", "набої", "патрони", "магазин до автомата",
        "обріз", "револьвер", "рушниця", "карабін",
        "гранатомет", "детонатор", "тротил"
    ],
    "вбивство": [
        "вбивство", "вбитий", "вбиті", "травми несумісні з життям",
        "смертельна рана", "застрелений", "застрелили", "зарізали",
        "загинув", "вбили", "помер від поранень",
        "смерть на місці", "виявили тіло", "труп",
        "тіло без ознак життя"
    ],
    "тілесні ушкодження": [
        "тілесні ушкодження", "ранений", "ТТУ", "тту",
        "важкі тілесні ушкодження", "смертельна рана",
        "вибухова травма", "вибухові травми", "колото різані рани",
        "рвана рана", "поранення", "кульове поранення",
        "підстрелили", "підрізали",
        "травми", "гематоми", "забої", "перелом",
        "ножове поранення", "проникаюче поранення",
        "тілесні", "побили", "побиття"
    ],
    "терористичний акт": [
        "терористичний акт", "теракт", "терорист", "терористи",
        "заклали вибухівку", "замінували",
        "заклали вибуховий пристрій", "підірвали вибухівку",
        "мінування", "повідомлення про мінування",
        "терористична загроза", "вибуховий пакет"
    ],
    "наркотики": [
        "наркотики", "наркота", "сбд", "кокаїн", "героїн",
        "марихуана", "кратом", "наркотичні речовини", "трава",
        "амфетамін", "метамфетамін", "канабіс", "солі",
        "психотропи", "психотропні речовини", "закладка",
        "збували наркотики", "зберігав наркотики"
    ],
    "дтп": [
        "дтп", "смертельна дтп", "аварія", "дорожньо транспортна пригода",
        "зіткнення автомобілів", "транспортна пригода",
        "наїзд на пішохода", "збив пішохода",
        "зіткнення", "перекинувся автомобіль", "перекинулося авто",
        "авто врізалося", "зіткнувся з", "дорожня аварія"
    ],
    "сзч": [
        "сзч", "самовільне залишення частини", "ухилянт", "дезертир",
        "втеча з частини", "самовільна відлучка", "дезертирство",
        "самовільно залишив частину", "залишив військову частину",
        "пішов у сзч", "самовільно покинув частину"
    ],
}

KEYWORD_TO_SHEET = {
    "поліція":            "поліція",
    "тцк":                "тцк",
    "підпал":             "підпал",
    "зброя":              "зброя",
    "вбивство":           "вбивство",
    "тілесні ушкодження": "тілесні ушкодження",
    "терористичний акт":  "терористичний акт",
    "наркотики":          "наркотики",
    "дтп":                "дтп",
    "сзч":                "сзч",
}

# Безпечна v2: ваги, пріоритети й м'які виключення поверх тих самих тем.
TOPIC_RULES = {
    "поліція": {
        "priority": 4,
        "threshold": 3,
        "strong": ["поліція", "патрульна поліція", "поліцейський", "поліцейські"],
        "medium": [
            "мвс", "поліцейського", "поліцейському", "поліцейська", "поліцейських",
            "правоохоронці", "правоохоронець", "слідчий", "слідчі"
        ],
        "weak": ["оперуповноважений", "наряд поліції", "екіпаж поліції", "поліцейський патруль"],
        "exclude": ["іграшкова поліція", "академія поліції", "фільм про поліцію"],
        "combo_bonus": [(["поліція", "затримали"], 2)],
    },
    "тцк": {
        "priority": 4,
        "threshold": 3,
        "strong": ["тцк", "тцк сп", "тцк та сп", "військомат", "військкомат"],
        "medium": [
            "військомату", "повістка", "повістки", "повістку", "резерв+",
            "мобілізаційне розпорядження", "вручення повістки", "вручили повістку"
        ],
        "weak": ["військовий облік", "оповіщення військовозобов'язаних"],
        "exclude": ["жарт про тцк", "мем про тцк"],
        "combo_bonus": [(["тцк", "повістка"], 2)],
    },
    "сзч": {
        "priority": 3,
        "threshold": 4,
        "strong": ["сзч", "самовільне залишення частини", "дезертирство", "пішов у сзч"],
        "medium": [
            "ухилянт", "дезертир", "втеча з частини", "самовільна відлучка",
            "самовільно залишив частину", "самовільно покинув частину"
        ],
        "weak": ["залишив військову частину"],
        "exclude": ["історичний фільм", "жарт"],
        "combo_bonus": [(["ухилянт", "втеча з частини"], 2)],
    },
    "зброя": {
        "priority": 7,
        "threshold": 4,
        "strong": [
            "зброя", "холодна зброя", "пістолет", "автомат", "граната", "вибухівка",
            "обріз", "револьвер", "рушниця", "карабін", "гранатомет"
        ],
        "medium": [
            "ніж", "кастет", "вибуховий пристрій", "заточка",
            "боєприпаси", "набої", "патрони", "магазин до автомата"
        ],
        "weak": ["предмет схожий на зброю", "детонатор", "тротил"],
        "exclude": ["іграшковий пістолет", "сувенірний ніж", "кухонний ніж"],
        "combo_bonus": [(["пістолет", "затримали"], 2), (["ніж", "поранення"], 3)],
    },
    "вбивство": {
        "priority": 10,
        "threshold": 5,
        "strong": [
            "вбивство", "вбитий", "вбиті", "застрелений", "застрелили", "зарізали",
            "вбили", "тіло без ознак життя"
        ],
        "medium": [
            "травми несумісні з життям", "смертельна рана", "загинув",
            "помер від поранень", "смерть на місці", "виявили тіло", "труп"
        ],
        "weak": [],
        "exclude": ["кіно", "серіал", "гра"],
        "combo_bonus": [(["загинув", "ножем"], 3), (["застрелили", "поліція"], 1)],
    },
    "тілесні ушкодження": {
        "priority": 9,
        "threshold": 5,
        "strong": [
            "тілесні ушкодження", "важкі тілесні ушкодження", "кульове поранення",
            "ножове поранення", "проникаюче поранення"
        ],
        "medium": [
            "ранений", "тту", "вибухова травма", "вибухові травми",
            "колото різані рани", "рвана рана", "поранення", "підстрелили", "підрізали",
            "травми", "гематоми", "забої", "перелом", "побили", "побиття"
        ],
        "weak": ["смертельна рана", "тілесні"],
        "exclude": ["спортивна травма", "побутова подряпина"],
        "combo_bonus": [(["поранення", "ніж"], 2), (["кульове поранення", "поліція"], 2)],
    },
    "наркотики": {
        "priority": 6,
        "threshold": 4,
        "strong": [
            "наркотики", "наркота", "кокаїн", "героїн", "марихуана",
            "наркотичні речовини", "амфетамін", "метамфетамін", "канабіс"
        ],
        "medium": ["кратом", "сбд", "солі", "психотропи", "психотропні речовини"],
        "weak": ["трава", "закладка", "збували наркотики", "зберігав наркотики"],
        "exclude": ["газонна трава", "лікарські трави"],
        "combo_bonus": [(["наркотики", "збували"], 2)],
    },
    "підпал": {
        "priority": 8,
        "threshold": 4,
        "strong": ["підпал", "підпали", "коктейль молотова", "умисний підпал", "підпалили"],
        "medium": [
            "пошкодження майна", "загоряння", "пожежа", "дснс", "рятівники", "мнс",
            "підпал авто", "підпал будинку", "підпалили автомобіль"
        ],
        "weak": ["пожежники", "займання"],
        "exclude": ["коротке замикання", "навчальна тривога"],
        "combo_bonus": [(["пожежа", "коктейль молотова"], 3), (["підпал", "авто"], 2)],
    },
    "дтп": {
        "priority": 7,
        "threshold": 4,
        "strong": ["дтп", "смертельна дтп", "дорожньо транспортна пригода", "дорожня аварія"],
        "medium": [
            "аварія", "зіткнення автомобілів", "транспортна пригода", "зіткнення",
            "перекинувся автомобіль", "перекинулося авто", "авто врізалося", "зіткнувся з"
        ],
        "weak": ["наїзд на пішохода", "збив пішохода"],
        "exclude": ["технічна аварія", "аварія на мережі"],
        "combo_bonus": [(["аварія", "загинув"], 3), (["дтп", "пішохід"], 2)],
    },
    "терористичний акт": {
        "priority": 10,
        "threshold": 5,
        "strong": ["терористичний акт", "теракт", "терорист", "терористи", "терористична загроза"],
        "medium": [
            "заклали вибухівку", "замінували", "заклали вибуховий пристрій",
            "підірвали вибухівку", "мінування", "повідомлення про мінування"
        ],
        "weak": ["вибуховий пакет"],
        "exclude": ["антитерористичні навчання", "жарт про мінування"],
        "combo_bonus": [(["теракт", "вибухівка"], 3), (["замінували", "евакуація"], 2)],
    },
}

SCORE_WEIGHTS = {
    "strong": 5,
    "medium": 3,
    "weak": 1,
    "exclude": -3,
}


def get_classifier_mode_label(mode: str) -> str:
    return CLASSIFIER_MODES.get(mode, CLASSIFIER_MODES["legacy"])


def normalize_text(text: str) -> str:
    text = (text or "").lower().replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _count_phrase_occurrences(text: str, phrase: str) -> int:
    phrase = normalize_text(phrase)
    if not phrase:
        return 0
    if " " in phrase or "+" in phrase:
        return text.count(phrase)
    pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"
    return len(re.findall(pattern, text))


def _collect_hits(text: str, phrases: list[str]) -> tuple[int, list[str]]:
    total = 0
    found = []
    for phrase in phrases:
        count = _count_phrase_occurrences(text, phrase)
        if count:
            total += count
            found.extend([phrase] * count)
    return total, found


def _pick_strongest_form(rule: dict, found_forms: list[str]) -> str | None:
    if not found_forms:
        return None
    for bucket in ("strong", "medium", "weak"):
        bucket_forms = rule.get(bucket, [])
        for form in bucket_forms:
            if form in found_forms:
                return form
    return found_forms[0]


def count_keyword_occurrences(text: str, keyword: str) -> int:
    normalized = normalize_text(text)
    forms = KEYWORD_FORMS.get(keyword, [keyword])
    total = 0
    for form in forms:
        total += _count_phrase_occurrences(normalized, form)
    return total


def find_all_matching_keywords(text: str, active_keywords: list, min_hits: int = 1) -> list[str]:
    matched = []
    for kw in active_keywords:
        hits = count_keyword_occurrences(text, kw)
        if hits >= min_hits:
            matched.append(kw)
    return matched


def find_matching_keyword(text: str, active_keywords: list, min_hits: int = 1):
    for kw in active_keywords:
        hits = count_keyword_occurrences(text, kw)
        if hits >= min_hits:
            return kw
    return None


def build_legacy_result(text: str, active_keywords: list, min_hits: int = 1) -> dict:
    matched = find_matching_keyword(text, active_keywords, min_hits=min_hits)
    found_forms = []
    other_topics = []
    if matched:
        _, found_forms = _collect_hits(normalize_text(text), KEYWORD_FORMS.get(matched, [matched]))
        all_topics = find_all_matching_keywords(text, active_keywords, min_hits=min_hits)
        other_topics = [topic for topic in all_topics if topic != matched]
    return {
        "matched": bool(matched),
        "main_topic": matched,
        "sheet_name": KEYWORD_TO_SHEET.get(matched) if matched else None,
        "score": count_keyword_occurrences(text, matched) if matched else 0,
        "confidence": "legacy",
        "found_forms": found_forms,
        "primary_form": found_forms[0] if found_forms else None,
        "secondary_topics": other_topics,
        "other_topics": other_topics,
        "debug": {matched: count_keyword_occurrences(text, matched)} if matched else {},
        "mode": "legacy",
    }


def _fallback_topic_rule(keyword: str) -> dict:
    return {
        "priority": 1,
        "threshold": 3,
        "strong": [],
        "medium": KEYWORD_FORMS.get(keyword, [keyword]),
        "weak": [],
        "exclude": [],
        "combo_bonus": [],
    }


def classify_post_v2(text: str, active_keywords: list) -> dict:
    normalized = normalize_text(text)
    candidates = []
    debug_scores = {}

    for keyword in active_keywords:
        rule = TOPIC_RULES.get(keyword, _fallback_topic_rule(keyword))
        score = 0
        found_forms = []

        for bucket in ("strong", "medium", "weak"):
            hits, forms = _collect_hits(normalized, rule.get(bucket, []))
            score += hits * SCORE_WEIGHTS[bucket]
            found_forms.extend(forms)

        exclude_hits, _ = _collect_hits(normalized, rule.get("exclude", []))
        score += exclude_hits * SCORE_WEIGHTS["exclude"]

        for combo_terms, bonus in rule.get("combo_bonus", []):
            if all(_count_phrase_occurrences(normalized, term) > 0 for term in combo_terms):
                score += bonus

        debug_scores[keyword] = score
        if score >= rule.get("threshold", 3) and found_forms:
            candidates.append({
                "topic": keyword,
                "sheet_name": KEYWORD_TO_SHEET.get(keyword),
                "score": score,
                "priority": rule.get("priority", 1),
                "found_forms": found_forms,
            })

    if not candidates:
        return {
            "matched": False,
            "main_topic": None,
            "sheet_name": None,
            "score": 0,
            "confidence": "none",
            "found_forms": [],
            "secondary_topics": [],
            "debug": debug_scores,
            "mode": "v2",
        }

    candidates.sort(key=lambda item: (item["score"], item["priority"]), reverse=True)
    best = candidates[0]
    secondary = [item["topic"] for item in candidates[1:] if item["score"] >= best["score"] - 2]
    other_topics = [item["topic"] for item in candidates[1:]]
    confidence = "low"
    threshold = TOPIC_RULES.get(best["topic"], _fallback_topic_rule(best["topic"])).get("threshold", 3)
    best_rule = TOPIC_RULES.get(best["topic"], _fallback_topic_rule(best["topic"]))
    primary_form = _pick_strongest_form(best_rule, best["found_forms"])
    if best["score"] >= threshold + 5:
        confidence = "high"
    elif best["score"] >= threshold + 2:
        confidence = "medium"

    return {
        "matched": True,
        "main_topic": best["topic"],
        "sheet_name": best["sheet_name"],
        "score": best["score"],
        "confidence": confidence,
        "found_forms": best["found_forms"],
        "primary_form": primary_form,
        "secondary_topics": secondary,
        "other_topics": other_topics,
        "debug": debug_scores,
        "mode": "v2",
    }


def compare_classifiers(text: str, active_keywords: list, min_hits: int = 1) -> dict:
    legacy = build_legacy_result(text, active_keywords, min_hits=min_hits)
    v2 = classify_post_v2(text, active_keywords)
    return {"legacy": legacy, "v2": v2}
