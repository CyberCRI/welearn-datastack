import logging
import math
import re
from functools import cache

from lingua import LanguageDetectorBuilder
from pyphen import Pyphen  # type: ignore

from welearn_datastack.constants import (
    DICT_READING_SPEEDS_LANG,
    FLESCH_KINCAID_CONSTANTS,
)

logger = logging.getLogger(__name__)


def remove_punctuation(text: str) -> str:
    """removes punctuation from text

    Args:
        text (str): text to evaluate

    Returns:
        str: text without punctuation
    """
    text = re.sub(r"\'(?![tsd]\b|ve\b|ll\b|re\b)", '"', text)
    # remove all punctuation except apostrophes
    punctuation_regex = r"[^\w\s\']"

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


def predict_readability(text: str, lang: str) -> str:
    """scores the readability with flesch reading ease (score from 0 to 100)

    Args:
        text (str): text to evaluate
        lang (str): 'en' or 'fr'

    Returns:
        float: flesch reading ease score
    """
    if lang not in FLESCH_KINCAID_CONSTANTS:
        return ""
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
        lang (code): 'en', 'fr', 'es'...

    Returns:
        int: number of seconds necessary to read text
    """
    pattern = r"\w+"
    n_words = len(re.findall(pattern, text))
    if lang in DICT_READING_SPEEDS_LANG:
        speed = DICT_READING_SPEEDS_LANG[lang]
    else:
        speed = DICT_READING_SPEEDS_LANG["en"]  # default reading speed
    ret = int(n_words / speed * 60)
    return str(ret)


@cache
def get_language_detector():
    """
    Returns a language detector instance.
    """
    return (
        LanguageDetectorBuilder.from_all_languages()
        .with_preloaded_language_models()
        .build()
    )
