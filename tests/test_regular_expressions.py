import re
import unittest

from welearn_datastack.regular_expression import (
    ALPHANUMERIC_DOT_REGEX,
    ANTI_URL_REGEX,
    BACKLINE_SEQUENCE_REGEX,
    BACKLINES_REGEX,
    BLANK_CHARACTERS_SEQUENCE_REGEX,
    LANG_CODE_IN_URL_REGEX,
    NON_ALPHANUMERIC_CHARACTER_REGEX,
    NON_CONTRACTION_APOSTROPHE_REGEX,
    SENTENCE_REGEX,
    SIMPLE_XML_ATTRIBUTE_REGEX,
    SINGLE_QUOTED_WORD_REGEX,
    SOFT_LINE_BREAK_REGEX,
    WHITESPACE_SEQUENCE_REGEX,
    WORD_CUT_BY_BACKLINES_REGEX,
    WORDS_REGEX,
    simple_xml_tag_format_regex,
)


class TestBacklinesRegex(unittest.TestCase):
    def test_matches_newline(self):
        self.assertRegex("\n", BACKLINES_REGEX)

    def test_matches_tab(self):
        self.assertRegex("\t", BACKLINES_REGEX)

    def test_matches_carriage_return(self):
        self.assertRegex("\r", BACKLINES_REGEX)

    def test_does_not_match_plain_text(self):
        self.assertIsNone(re.search(BACKLINES_REGEX, "hello world"))

    def test_replaces_all_backlines(self):
        result = re.sub(BACKLINES_REGEX, " ", "line1\nline2\ttab\r")
        self.assertEqual(result, "line1 line2 tab ")


class TestAntiUrlRegex(unittest.TestCase):
    def test_matches_http_url(self):
        self.assertRegex("https://example.com", ANTI_URL_REGEX)

    def test_matches_ftp_url(self):
        self.assertRegex("ftp://files.example.com/file.txt", ANTI_URL_REGEX)

    def test_matches_www_url(self):
        self.assertRegex("www.example.com", ANTI_URL_REGEX)

    def test_matches_url_with_path(self):
        self.assertRegex("https://example.com/path/to/page?q=1", ANTI_URL_REGEX)

    def test_matches_url_in_parentheses(self):
        self.assertRegex("(https://example.com)", ANTI_URL_REGEX)

    def test_does_not_match_plain_text(self):
        self.assertIsNone(re.search(ANTI_URL_REGEX, "just some text"))

    def test_removes_url_from_sentence(self):
        text = "Visit https://example.com for more info."
        result = re.sub(ANTI_URL_REGEX, "", text)
        self.assertNotIn("https://", result)


class TestSingleQuotedWordRegex(unittest.TestCase):
    def test_matches_single_quoted_word(self):
        m = re.search(SINGLE_QUOTED_WORD_REGEX, "'example'")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "example")

    def test_extracts_inner_word(self):
        result = re.sub(SINGLE_QUOTED_WORD_REGEX, r"\1", "He said 'hello' to her.")
        self.assertEqual(result, "He said hello to her.")

    def test_does_not_match_numbers_in_quotes(self):
        self.assertIsNone(re.search(SINGLE_QUOTED_WORD_REGEX, "'123'"))

    def test_does_not_match_unquoted_word(self):
        self.assertIsNone(re.search(SINGLE_QUOTED_WORD_REGEX, "example"))

    def test_does_not_match_multi_word_quotes(self):
        self.assertIsNone(re.search(SINGLE_QUOTED_WORD_REGEX, "'hello world'"))


class TestLangCodeInUrlRegex(unittest.TestCase):
    def test_extracts_lang_code(self):
        m = re.search(LANG_CODE_IN_URL_REGEX, "https://en.wikipedia.org/wiki/Example")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "en")

    def test_extracts_fr_lang_code(self):
        m = re.search(LANG_CODE_IN_URL_REGEX, "https://fr.wikipedia.org/wiki/Exemple")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "fr")

    def test_does_not_match_non_https(self):
        self.assertIsNone(re.search(LANG_CODE_IN_URL_REGEX, "http://en.example.com"))

    def test_does_not_match_plain_text(self):
        self.assertIsNone(re.search(LANG_CODE_IN_URL_REGEX, "no url here"))


class TestWordCutByBacklinesRegex(unittest.TestCase):
    def test_rejoins_hyphenated_word(self):
        result = re.sub(WORD_CUT_BY_BACKLINES_REGEX, "", "exam-\nple")
        self.assertEqual(result, "example")

    def test_rejoins_with_spaces(self):
        result = re.sub(WORD_CUT_BY_BACKLINES_REGEX, "", "exam-  \n  ple")
        self.assertEqual(result, "example")

    def test_does_not_match_simple_hyphen(self):
        self.assertIsNone(re.search(WORD_CUT_BY_BACKLINES_REGEX, "well-known"))

    def test_does_not_match_newline_without_hyphen(self):
        self.assertIsNone(re.search(WORD_CUT_BY_BACKLINES_REGEX, "line1\nline2"))


class TestSoftLineBreakRegex(unittest.TestCase):
    def test_matches_newline_after_regular_word(self):
        self.assertIsNotNone(re.search(SOFT_LINE_BREAK_REGEX, "word\nnext"))

    def test_does_not_match_after_period(self):
        self.assertIsNone(re.search(SOFT_LINE_BREAK_REGEX, "end.\nnext"))

    def test_does_not_match_after_question_mark(self):
        self.assertIsNone(re.search(SOFT_LINE_BREAK_REGEX, "end?\nnext"))

    def test_does_not_match_after_exclamation(self):
        self.assertIsNone(re.search(SOFT_LINE_BREAK_REGEX, "end!\nnext"))

    def test_does_not_match_after_colon(self):
        self.assertIsNone(re.search(SOFT_LINE_BREAK_REGEX, "end:\nnext"))

    def test_replaces_soft_line_break_with_space(self):
        result = re.sub(SOFT_LINE_BREAK_REGEX, " ", "word\nnext")
        self.assertEqual(result, "word next")


class TestBlankCharactersSequenceRegex(unittest.TestCase):
    def test_matches_multiple_spaces(self):
        self.assertRegex("   ", BLANK_CHARACTERS_SEQUENCE_REGEX)

    def test_matches_mixed_whitespace(self):
        self.assertRegex(" \t \n ", BLANK_CHARACTERS_SEQUENCE_REGEX)

    def test_collapses_spaces(self):
        result = re.sub(BLANK_CHARACTERS_SEQUENCE_REGEX, " ", "too   many   spaces")
        self.assertEqual(result, "too many spaces")

    def test_does_not_match_empty_string(self):
        self.assertIsNone(re.search(BLANK_CHARACTERS_SEQUENCE_REGEX, ""))


class TestAlphanumericDotRegex(unittest.TestCase):
    def test_matches_word(self):
        self.assertRegex("hello", ALPHANUMERIC_DOT_REGEX)

    def test_matches_word_with_dot(self):
        self.assertRegex("hello.world", ALPHANUMERIC_DOT_REGEX)

    def test_matches_alphanumeric(self):
        self.assertRegex("abc123", ALPHANUMERIC_DOT_REGEX)

    def test_does_not_match_special_chars(self):
        self.assertIsNone(re.fullmatch(ALPHANUMERIC_DOT_REGEX, "hello!"))

    def test_does_not_match_space(self):
        self.assertIsNone(re.fullmatch(ALPHANUMERIC_DOT_REGEX, "hello world"))


class TestSimpleXmlAttributeRegex(unittest.TestCase):
    def test_matches_simple_attribute(self):
        m = re.search(SIMPLE_XML_ATTRIBUTE_REGEX, 'lang="en"')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "lang")
        self.assertEqual(m.group(2), "en")

    def test_matches_namespaced_attribute(self):
        m = re.search(SIMPLE_XML_ATTRIBUTE_REGEX, 'xml:lang="fr"')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "xml:lang")

    def test_matches_empty_value(self):
        m = re.search(SIMPLE_XML_ATTRIBUTE_REGEX, 'attr=""')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "")

    def test_does_not_match_no_quotes(self):
        self.assertIsNone(re.search(SIMPLE_XML_ATTRIBUTE_REGEX, "attr=value"))


class TestWhitespaceSequenceRegex(unittest.TestCase):
    def test_matches_multiple_spaces(self):
        self.assertRegex("   ", WHITESPACE_SEQUENCE_REGEX)

    def test_does_not_match_newline(self):
        self.assertIsNone(re.search(WHITESPACE_SEQUENCE_REGEX, "\n"))

    def test_collapses_spaces(self):
        result = re.sub(WHITESPACE_SEQUENCE_REGEX, " ", "too   many   spaces")
        self.assertEqual(result, "too many spaces")


class TestBacklineSequenceRegex(unittest.TestCase):
    def test_matches_multiple_newlines(self):
        self.assertRegex("\n\n\n", BACKLINE_SEQUENCE_REGEX)

    def test_collapses_newlines(self):
        result = re.sub(BACKLINE_SEQUENCE_REGEX, "\n", "line1\n\n\nline2")
        self.assertEqual(result, "line1\nline2")

    def test_does_not_match_space(self):
        self.assertIsNone(re.search(BACKLINE_SEQUENCE_REGEX, " "))


class TestNonContractionApostropheRegex(unittest.TestCase):
    def test_does_not_match_contraction_not(self):
        # "don't" -> 't contraction, should not match
        self.assertIsNone(re.search(NON_CONTRACTION_APOSTROPHE_REGEX, "don't"))

    def test_does_not_match_contraction_ve(self):
        self.assertIsNone(re.search(NON_CONTRACTION_APOSTROPHE_REGEX, "I've"))

    def test_does_not_match_contraction_ll(self):
        self.assertIsNone(re.search(NON_CONTRACTION_APOSTROPHE_REGEX, "I'll"))

    def test_does_not_match_contraction_re(self):
        self.assertIsNone(re.search(NON_CONTRACTION_APOSTROPHE_REGEX, "they're"))

    def test_does_not_match_contraction_s(self):
        self.assertIsNone(re.search(NON_CONTRACTION_APOSTROPHE_REGEX, "it's"))


class TestNonAlphanumericCharacterRegex(unittest.TestCase):
    def test_matches_special_character(self):
        self.assertIsNotNone(re.search(NON_ALPHANUMERIC_CHARACTER_REGEX, "hello@world"))

    def test_matches_exclamation(self):
        self.assertIsNotNone(re.search(NON_ALPHANUMERIC_CHARACTER_REGEX, "wow!"))

    def test_does_not_match_decimal_dot(self):
        self.assertIsNone(re.search(NON_ALPHANUMERIC_CHARACTER_REGEX, "3.14"))

    def test_does_not_match_alphanumeric(self):
        self.assertIsNone(re.search(NON_ALPHANUMERIC_CHARACTER_REGEX, "hello world"))

    def test_does_not_match_apostrophe(self):
        self.assertIsNone(re.search(NON_ALPHANUMERIC_CHARACTER_REGEX, "don't"))

    def test_removes_special_chars(self):
        result = re.sub(NON_ALPHANUMERIC_CHARACTER_REGEX, "", "hello#world!")
        self.assertEqual(result, "helloworld")


class TestSentenceRegex(unittest.TestCase):
    def test_matches_simple_sentence(self):
        matches = re.findall(SENTENCE_REGEX, "Hello world.")
        self.assertTrue(len(matches) >= 1)

    def test_matches_multiple_sentences(self):
        matches = re.findall(SENTENCE_REGEX, "Hello. How are you? Fine!")
        self.assertEqual(len(matches), 3)

    def test_matches_sentence_without_punctuation(self):
        matches = re.findall(SENTENCE_REGEX, "No punctuation here")
        self.assertTrue(len(matches) >= 1)


class TestWordsRegex(unittest.TestCase):
    def test_matches_word(self):
        self.assertRegex("hello", WORDS_REGEX)

    def test_finds_all_words(self):
        words = re.findall(WORDS_REGEX, "Hello world 123")
        self.assertEqual(words, ["Hello", "world", "123"])

    def test_ignores_punctuation(self):
        words = re.findall(WORDS_REGEX, "Hello, world!")
        self.assertEqual(words, ["Hello", "world"])


class TestSimpleXmlTagFormatRegex(unittest.TestCase):
    def test_matches_simple_tag(self):
        pattern = simple_xml_tag_format_regex("title")
        m = re.search(pattern, "<title>My Title</title>", re.DOTALL)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "My Title")

    def test_matches_tag_with_attributes(self):
        pattern = simple_xml_tag_format_regex("doc")
        m = re.search(pattern, '<doc lang="en">content</doc>', re.DOTALL)
        self.assertIsNotNone(m)
        self.assertIn("lang", m.group(1))
        self.assertEqual(m.group(2), "content")

    def test_matches_multiline_content(self):
        pattern = simple_xml_tag_format_regex("body")
        m = re.search(pattern, "<body>line1\nline2</body>", re.DOTALL)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "line1\nline2")

    def test_does_not_match_wrong_tag(self):
        pattern = simple_xml_tag_format_regex("title")
        self.assertIsNone(re.search(pattern, "<body>content</body>"))

    def test_does_not_match_unclosed_tag(self):
        pattern = simple_xml_tag_format_regex("title")
        self.assertIsNone(re.search(pattern, "<title>content"))

    def test_returns_correct_regex_type(self):
        pattern = simple_xml_tag_format_regex("p")
        self.assertIsInstance(pattern, str)
