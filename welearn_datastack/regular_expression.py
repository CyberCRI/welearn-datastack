# Regular expressions for data cleaning and preprocessing in the WeLearn Datastack project.

# Regular expression to match backlines (newline, tab, carriage return)
BACKLINES_REGEX = r"([\n\t\r])"

# Regular expression to match URLs, including optional parentheses around them
ANTI_URL_REGEX = r"\(?((www)|((https?|ftp|file):\/\/))[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]\)?"

# Regular expression to match words that are between single quotes, e.g., "'example'" -> "example"
SINGLE_QUOTED_WORD_REGEX = r"'([A-Za-z]+)'"

# Regular expression to match language code in URL, e.g., "https://en.wikipedia.org/wiki/Example" -> "en"
LANG_CODE_IN_URL_REGEX = r"https://([a-z]{2})"

# Regular expression to match words that are cut by backlines, e.g., "exam-\nple" -> "example"
WORD_CUT_BY_BACKLINES_REGEX = r"-\s*\n\s*"

SOFT_LINE_BREAK_REGEX = r"(?<![\.\:\?\!])\s*\n\s*"

BLANK_CHARACTERS_SEQUENCE_REGEX = r"\s+"

ALPHANUMERIC_DOT_REGEX = r"^[\w.]+$"

# Pattern to capture the attributes of the tag in the form of key="value"
SIMPLE_XML_ATTRIBUTE_REGEX = r'([\w:]+)="([^"]*)"'

WHITESPACE_SEQUENCE_REGEX = r" +"

BACKLINE_SEQUENCE_REGEX = r"\n+"

NON_CONTRACTION_APOSTROPHE_REGEX = r"\'(?![tsd]\b|ve\b|ll\b|re\b)"

NON_ALPHANUMERIC_CHARACTER_REGEX = r"[^\w\s'\.,]|(?<!\d)[.,](?!\d)"

SENTENCE_REGEX = r"\b[^.!?]+[.!?]*"

WORDS_REGEX = r"\w+"


def simple_xml_tag_format_regex(tag: str) -> str:
    """
    Generate a regular expression to match a simple XML tag with the given name.
    The tag is expected to have the format <tag>content</tag> without attributes.

    :param tag: The name of the XML tag to match.
    :return: A regular expression string to match the specified XML tag.
    """
    return rf"<{tag}([^>]*)>(.*?)</{tag}>"
