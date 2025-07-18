import logging
from typing import List, Tuple

from pypdf import PdfReader
from refinedoc.refined_document import RefinedDocument

logger = logging.getLogger(__name__)


def large_pages_size_flag(reader: PdfReader, limit: int) -> Tuple[List[int], bool]:
    """
    Check the size of a PDF document page
    :param limit: In byte, limit the pdf need to not exceed
    :param reader: The PDF document already opened. Each page gonna be processed.
    :return: List of sizes for each page (index in the list equal index in pdf) and if one of this exceed limit
    """
    logger.info(f"Size limit for each page : {limit}")
    ret = []
    number_of_pages = len(reader.pages)
    logger.info(f"Test size of {number_of_pages} pages")
    flag = False
    for i in range(number_of_pages):
        page = reader.pages[i]
        page_size = len(page.get_contents().get_data())  # type: ignore
        ret.append(page_size)
        if page_size > limit:
            flag = True

    return ret, flag


def extract_txt_from_pdf(
    reader: PdfReader, remove_headers: bool = True, remove_footers: bool = True
) -> List[List[str]]:
    """
    Extract the text from a PDF document and return it as a list of strings for each page of the document and a list of
    strings for each page for a filtered document and the reference document (extracted with PyPDF)

    :param reader: the PDF reader object
    :return: a tuple containing the extracted & filtered text
    """
    pdf_content: List[List[str]] = []
    for page in reader.pages:
        text = page.extract_text().split("\n")
        page_content = [t.strip() for t in text if t.strip()]
        pdf_content.append(page_content)

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
