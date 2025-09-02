import io
import logging
from typing import List

from refinedoc.refined_document import RefinedDocument

from welearn_datastack.modules.tika_client import TikaClient

logger = logging.getLogger(__name__)


def extract_txt_from_pdf_with_tika(
    pdf_content: io.BytesIO, tika_base_url: str
) -> List[List[str]]:
    """
    Extract the text from a PDF document and return it as a list of strings for each page of the document and a list of
    strings for each page for a filtered document and the reference document (extracted with tika micro service)

    :param pdf_content: the PDF document content as a byte stream
    :param tika_base_url: the base URL of the Tika micro service
    :return: Matrix of strings (list of list of strings) for each page of the document
    """
    client = TikaClient()
    tika_content = client.tika(pdf_content)
    pdf_content = client.parse_tika_content(tika_content)

    refined_pdf_content = RefinedDocument(content=pdf_content)

    return refined_pdf_content.body


def delete_non_printable_character(text: str) -> str:
    """
    Delete non-printable characters from a text

    :param text: the text to clean

    :return: the cleaned text
    """
    return "".join([c for c in text if c.isprintable()])


def replace_ligatures(text: str) -> str:
    """
    Replace ligatures in text by their equivalent

    :param text: the text to clean

    :return: the cleaned text
    """
    ligatures = {
        "ﬀ": "ff",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "ft",
        "ﬆ": "st",
        # "Ꜳ": "AA",
        # "Æ": "AE",
        "ꜳ": "aa",
    }
    for search, replace in ligatures.items():
        text = text.replace(search, replace)
    return text


def delete_accents(text: str) -> str:
    """
    Delete accents in text

    :param text: the text to clean

    :return: the cleaned text
    """
    accents = {
        "´": "",
        "`": "",
        "ˆ": "",
        "˜": "",
        "¸": "",
        "˚": "",
        "¨": "",
        "˝": "",
        "˛": "",
        "˙": "",
        "ˇ": "",
        "˘": "",
    }
    for search, replace in accents.items():
        local_search_items = [f" {search}", f"{search} ", f"{search}"]
        for search_item in local_search_items:
            text = text.replace(search_item, replace)
    return text


def remove_hyphens(text: str) -> str:
    """
    This fails for:
    * Natural dashes: well-known, self-replication, use-cases, non-semantic,
                      Post-processing, Window-wise, viewpoint-dependent
    * Trailing math operands: 2 - 4
    * Names: Lopez-Ferreras, VGG-19, CIFAR-100
    """
    lines = [line.rstrip() for line in text.split("\n")]

    # Find dashes
    line_numbers = []
    for line_no, line in enumerate(lines[:-1]):
        if line.endswith("-"):
            line_numbers.append(line_no)

    # Replace
    for line_no in line_numbers:
        lines = _dehyphenate(lines, line_no)

    return "\n".join(lines)


def _dehyphenate(lines: List[str], line_no: int) -> List[str]:
    """
    Dehyphenate a line in a list of lines

    :param lines: the list of lines
    :param line_no: the line number to dehyphenate

    :return: the list of lines with the dehyphenated line
    """
    next_line = lines[line_no + 1]
    word_suffix = next_line.split(" ")[0]

    lines[line_no] = lines[line_no][:-1] + word_suffix
    lines[line_no + 1] = lines[line_no + 1][len(word_suffix) :]
    return lines
