# Regular expressions for data cleaning and preprocessing in the WeLearn Datastack project.

# description: Matches backline characters (newline, tab, carriage return) for removal or replacement.
# example: "Hello\n\tWorld" -> matches "\n" and "\t"
# limit: Does not match other whitespace characters like spaces or form feeds.
BACKLINES_REGEX = r"([\n\t\r])"

# description: Matches URLs with optional surrounding parentheses, supporting http, https, ftp, file, and www prefixes.
# example: "Visit (https://example.com) for more." -> matches "(https://example.com)"
# limit: May miss URLs using uncommon schemes or those ending with punctuation that is part of the URL.
ANTI_URL_REGEX = r"\(?((www)|((https?|ftp|file):\/\/))[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]\)?"

# description: Matches a single alphabetic word wrapped in single quotes, capturing the word without the quotes.
# example: "'example'" -> captures "example"
# limit: Only matches purely alphabetic words; digits, hyphens, or other characters inside quotes are not matched.
SINGLE_QUOTED_WORD_REGEX = r"'([A-Za-z]+)'"

# description: Matches the two-letter language code subdomain in a Wikipedia-style URL.
# example: "https://en.wikipedia.org/wiki/Example" -> captures "en"
# limit: Only matches exactly two lowercase letters; will not capture longer or uppercase subdomains.
LANG_CODE_IN_URL_REGEX = r"https://([a-z]{2})"

# description: Matches a hyphen followed by optional whitespace and a newline, used to rejoin words split across lines.
# example: "exam-\nple" -> matches "-\n" so it can be replaced to reconstruct "example"
# limit: Does not account for intentional hyphens at line breaks that should remain (e.g., compound words).
WORD_CUT_BY_BACKLINES_REGEX = r"-\s*\n\s*"

# description: Matches a soft line break — a newline not preceded by a sentence-ending punctuation mark.
# example: "Hello\nWorld" (no period before \n) -> matches "\nWorld"; "Hello.\nWorld" -> no match
# limit: Only checks for . : ? ! as sentence-ending characters; other terminators (e.g., ellipsis) are ignored.
SOFT_LINE_BREAK_REGEX = r"(?<![\.\:\?\!])\s*\n\s*"

# description: Matches any sequence of one or more whitespace characters (spaces, tabs, newlines, etc.).
# example: "Hello   World" -> matches "   "
# limit: Treats all whitespace types uniformly; cannot distinguish between spaces and newlines.
BLANK_CHARACTERS_SEQUENCE_REGEX = r"\s+"

# description: Matches strings composed exclusively of word characters (letters, digits, underscore) and dots.
# example: "hello.world" -> matches; "hello world" -> no match
# limit: The dot is not escaped, so it matches any character in some contexts; relies on anchors ^ and $ for full-string validation.
ALPHANUMERIC_DOT_REGEX = r"^[\w.]+$"

# description: Matches a key="value" attribute pair inside an XML or HTML tag.
# example: 'lang="en"' -> captures ("lang", "en")
# limit: Only handles double-quoted values; single-quoted or unquoted attributes are not matched.
SIMPLE_XML_ATTRIBUTE_REGEX = r'([\w:]+)="([^"]*)"'

# description: Matches a sequence of two or more space characters (not tabs or newlines).
# example: "Hello   World" -> matches "   "
# limit: Only matches literal space characters; other whitespace (tabs, newlines) is excluded.
WHITESPACE_SEQUENCE_REGEX = r" +"

# description: Matches one or more consecutive newline characters to detect or collapse blank lines.
# example: "Hello\n\n\nWorld" -> matches "\n\n\n"
# limit: Does not match other vertical whitespace like carriage returns (\r) unless combined with \n.
BACKLINE_SEQUENCE_REGEX = r"\n+"

# description: Matches an apostrophe that is NOT part of a common English contraction suffix.
# example: "it's" -> no match; "the '90s" -> matches "'"
# limit: Only accounts for a fixed list of contraction suffixes (t, s, d, ve, ll, re); less common contractions may be incorrectly matched.
NON_CONTRACTION_APOSTROPHE_REGEX = r"\'(?![tsd]\b|ve\b|ll\b|re\b)"

# description: Matches non-alphanumeric characters excluding spaces, apostrophes, and dots/commas when adjacent to digits.
# example: "Hello! World" -> matches "!"; "3.14" -> dot not matched; "e.g.," -> comma matched
# limit: The logic for preserving dots and commas near digits may produce unexpected results in edge cases like ".5" or "1,000,000".
NON_ALPHANUMERIC_CHARACTER_REGEX = r"[^\w\s'\.,]|(?<!\d)[.,](?!\d)"

# description: Matches a sentence as a sequence of non-punctuation characters optionally terminated by . ! or ?.
# example: "Hello world. How are you?" -> matches "Hello world." and " How are you?"
# limit: Does not handle abbreviations, ellipses, or multi-sentence structures with nested punctuation correctly.
SENTENCE_REGEX = r"\b[^.!?]+[.!?]*"

# description: Matches one or more word characters (letters, digits, underscore), effectively tokenizing words.
# example: "Hello, world!" -> matches "Hello" and "world"
# limit: Treats underscores as word characters and does not handle hyphenated words or contractions as single tokens.
WORDS_REGEX = r"\w+"


def simple_xml_tag_format_regex(tag: str) -> str:
    """
    description: Generates a regex to match a simple XML tag with its content and optional attributes.
    example: simple_xml_tag_format_regex("title") matches '<title lang="en">Hello</title>', capturing (' lang="en"', 'Hello').
    limit: Uses a non-greedy match for content, so it may behave unexpectedly with nested tags of the same name.

    :param tag: The name of the XML tag to match.
    :return: A regular expression string to match the specified XML tag.
    """
    return rf"<{tag}([^>]*)>(.*?)</{tag}>"
