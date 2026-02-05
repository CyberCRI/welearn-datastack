import logging
import math
import os
import re
from collections import deque
from dataclasses import asdict, is_dataclass
from functools import cache

from lingua import LanguageDetectorBuilder
from pyphen import Pyphen
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import (
    DICT_READING_SPEEDS_LANG,
    FLESCH_KINCAID_CONSTANTS,
)

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError("Log level is not recognized : '%s'", log_level)

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


# Utils
@cache
def get_language_detector():
    """
    Returns a language detector instance.
    """
    return (
        LanguageDetectorBuilder.from_all_spoken_languages()
        .with_low_accuracy_mode()
        .build()
    )


def remove_punctuation(text: str) -> str:
    """removes punctuation from text

    Args:
        text (str): text to evaluate

    Returns:
        str: text without punctuation
    """
    text = re.sub(r"\'(?![tsd]\b|ve\b|ll\b|re\b)", '"', text)
    # remove all punctuation except apostrophes
    punctuation_regex = r"[^\w\s'\.,]|(?<!\d)[.,](?!\d)"

    text = re.sub(punctuation_regex, "", text)
    return text


def lexicon_count(text: str) -> int:
    """returns the number of words in text

    Args:
        text (str): text to evaluate

    Returns:
        int: number of words in text
    """
    text = remove_punctuation(text)
    count = len(text.split())
    return count


def sentence_count(text: str) -> int:
    """returns the number of sentences in text

    Args:
        text (str): text to evaluate

    Returns:
        int: number of sentences in text
    """
    ignore_count = 0
    sentences = re.findall(r"\b[^.!?]+[.!?]*", text, re.UNICODE)
    for sentence in sentences:
        if lexicon_count(sentence) <= 2:
            ignore_count += 1
    return max(1, len(sentences) - ignore_count)


def avg_sentence_length(text: str) -> float:
    """returns the average number of words per sentence in text

    Args:
        text (str): text to evaluate

    Returns:
        float: average number of words per sentence
    """
    try:
        return float(lexicon_count(text) / sentence_count(text))
    except ZeroDivisionError:
        return 0.0


def syllable_count(text: str, lang: str) -> int:
    """returns the number of syllables in text

    Args:
        text (str): text to evaluate
        lang (str): 'en' or 'fr'

    Returns:
        int: number of syllables in text
    """
    text = text.lower()
    text = remove_punctuation(text)

    if not text:
        return 0

    count = 0
    pyphen = Pyphen(lang=lang)
    for word in text.split():
        count += len(pyphen.positions(word)) + 1
    return count


def avg_syllables_per_word(text: str, lang: str) -> float:
    """returns the average number of syllables per word in text

    Args:
        text (str): text to evaluate
        lang (str): 'en' or 'fr'

    Returns:
        float: average number of syllables per word
    """
    syllable = syllable_count(text, lang)
    words = lexicon_count(text)
    try:
        return float(syllable) / float(words)
    except ZeroDivisionError:
        return 0.0


def predict_readability(text: str, lang: str) -> str | None:
    """scores the readability with flesch reading ease (score from 0 to 100)

    Args:
        text (str): text to evaluate
        lang (str): supported language code, e.g. 'en', 'fr', 'de', 'es', 'it', 'nl'

    Returns:
        float: flesch reading ease score
    """
    if lang not in FLESCH_KINCAID_CONSTANTS:
        return None
    fre_base = FLESCH_KINCAID_CONSTANTS[lang]["fre_base"]
    fre_sentence_length = FLESCH_KINCAID_CONSTANTS[lang]["fre_sentence_length"]
    fre_syll_per_word = FLESCH_KINCAID_CONSTANTS[lang]["fre_syll_per_word"]

    flesch = (
        fre_base
        - fre_sentence_length * avg_sentence_length(text)
        - fre_syll_per_word * avg_syllables_per_word(text, lang)
    )
    flesch = float(math.floor((flesch * 100) + math.copysign(0.5, flesch))) / 100
    ret = min(100.0, max(0.0, flesch))

    return str(ret)


def predict_duration(text: str, lang: str) -> str:
    """Estimate the reading time in seconds necessary to read a text

    Args:
        text (str): text for which to evaluate reading time
        lang (code): supported language code, e.g. 'en', 'fr', 'de', 'es', 'it', 'nl', 'jp', 'pt', 'ar', 'zh'

    Returns:
        int: number of seconds necessary to read text
    """
    pattern = r"\w+"
    n_words = len(re.findall(pattern, text))
    speed = DICT_READING_SPEEDS_LANG.get(
        lang, 184
    )  # 184 is the average of reading speeds from https://irisreading.com/average-reading-speed-in-various-languages/
    ret = int(n_words / speed * 60)
    return str(ret)


# Methods
def identify_document_language(document: WeLearnDocument) -> WeLearnDocument:
    if document.lang:
        return document

    lang_detector = get_language_detector()
    confidence_values_content = deque(
        lang_detector.compute_language_confidence_values(document.full_content)
    )
    confidence_values_desc = deque(
        lang_detector.compute_language_confidence_values(document.description)
    )

    document_lang = (
        confidence_values_content.popleft().language.iso_code_639_1.name.lower()
    )
    desc_lang = confidence_values_desc.popleft().language.iso_code_639_1.name.lower()
    content_and_description_different_language = document_lang != desc_lang

    if content_and_description_different_language:
        logger.warning(
            f"Content and description languages are different: {document_lang} vs {desc_lang} for document {document.id}"
        )
    document.lang = document_lang
    document.details["content_and_description_lang"] = {
        "are_different": content_and_description_different_language,
        "description": {
            "language": desc_lang,
            "confidence": confidence_values_desc.popleft().value,
        },
        "content": {
            "language": document_lang,
            "confidence": confidence_values_content.popleft().value,
        },
    }

    return document


def compute_duration(
    document: WeLearnDocument, strict: bool = False
) -> WeLearnDocument:
    """
    Computes the estimated reading duration for a document and updates its details.
    :param document: WeLearnDocument object to compute duration for
    :param strict: If True, recompute duration even if it already exists

    :return: Updated WeLearnDocument with estimated duration in details
    """
    if not strict and "duration" in document.details:
        return document

    document.details["duration"] = predict_duration(
        document.full_content, document.lang
    )
    return document


def compute_readability(
    document: WeLearnDocument, strict: bool = False
) -> WeLearnDocument:
    """
    Computes the readability score for a document and updates its details.

    :param document: WeLearnDocument object to compute readability for
    :param strict: If True, recompute readability even if it already exists

    :return: Updated WeLearnDocument with readability score in details
    """
    if not strict and "readability" in document.details:
        return document

    document.details["readability"] = predict_readability(
        document.full_content, document.lang
    )
    return document


def is_dataclass_instance(obj):
    return is_dataclass(obj) and not isinstance(obj, type)


def _inner_serialize_dataclass(value):
    match value:
        case list():
            return [_inner_serialize_dataclass(item) for item in value]
        case dict():
            return {k: _inner_serialize_dataclass(v) for k, v in value.items()}
    if is_dataclass_instance(value):
        return asdict(value)
    return value


def serialize_dataclass_instance(document: WeLearnDocument) -> WeLearnDocument:
    for detail_key, detail_value in document.details.items():
        match detail_value:
            case list():
                document.details[detail_key] = [
                    _inner_serialize_dataclass(item) for item in detail_value
                ]
            case dict():
                for k, v in detail_value.items():
                    detail_value[k] = _inner_serialize_dataclass(v)
                document.details[detail_key] = detail_value
            case _:
                document.details[detail_key] = _inner_serialize_dataclass(detail_value)
    return document
