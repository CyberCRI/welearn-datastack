import logging
from copy import deepcopy
from typing import List, Tuple

from pypdf import PdfReader

from welearn_datastack.data.enumerations import DeletePart
from welearn_datastack.data.pdf_body_info import PDFBodyInfo

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


def extract_txt_from_pdf(reader: PdfReader) -> Tuple[List[List[str]], List[List[str]]]:
    """
    Extract the text from a PDF document and return it as a list of strings for each page of the document and a list of
    strings for each page for a filtered document and the reference document (extracted with PyPDF)

    :param reader: the PDF reader object
    :return: a tuple containing the extracted & filtered text and the reference text
    """
    pdf_content = []
    ref_content = []
    number_of_pages = len(reader.pages)
    body_info = PDFBodyInfo(pdf_reader=reader)

    for i in range(number_of_pages):
        page = reader.pages[i]
        parts: List[str] = []

        def get_text(text, cm, tm, font_dict, font_size):
            """
            Helper method used by visitor text to get the text according a set of filter

            Parameters
            ----------
            text : str
                the text of the character
            cm : List[float]
                the character matrix
            tm : List[float]
                the text matrix
            font_dict : Dict
                the font dictionary
            font_size : float
                the font size
            """

            character_height = round(font_size, 0)
            min_height = min(body_info.body_range)

            # x and y can be found in these two matrix without any logic
            x = round(max([cm[4], tm[4]]), 0)
            y = round(max([cm[5], tm[5]]), 0)

            # Filters :
            # Check if the character height is in the body range
            # Check if the text is not empty
            # Check if the text is in the body position
            if (
                character_height >= min_height
                and text != ""
                and x >= body_info.most_used_x
                and body_info.margin_top_y(page_number=i)
                >= y
                >= body_info.margin_bottom_y(page_number=i)
            ):
                parts.append(text)

        reference_text = page.extract_text(
            orientations=0,
            visitor_text=get_text,
            space_width=200,
            layout_mode_space_vertically=False,
        )

        extracted_text = " ".join(parts)
        extracted_text.replace("- ", "")
        pdf_content.append(extracted_text.split("\n"))
        ref_content.append(reference_text.split("\n"))

    return pdf_content, ref_content


def delete_pages(
    pdf_content: List[List[str]],
    indication: DeletePart,
    key: str,
    ref_content: List[List[str]] | None = None,
):
    """
    Delete pages from a PDF document according to a key and an indication

    :param pdf_content: the content of the PDF document
    :param indication: the indication to delete
    :param key: the key to delete
    :param ref_content: the reference content of the PDF document

    :return: The pointer is directly modified
    """
    if not ref_content:
        ref_content = pdf_content

    for page_number in range(len(ref_content)):
        messy_content = deepcopy(ref_content[page_number])
        content = [word.lower().strip() for word in messy_content]

        key = key.lower().strip()
        if key in content:
            if indication == DeletePart.before:
                # Delete even in the current page
                key_index = content.index(key)
                del pdf_content[page_number][: key_index + 1]
                del ref_content[page_number][: key_index + 1]

                # Delete useless pages
                for i in range(page_number):
                    del pdf_content[0]
                    del ref_content[0]

            elif indication == DeletePart.after:
                # Delete even in the current page
                key_index = content.index(key)
                del pdf_content[page_number][key_index:]
                del ref_content[page_number][key_index:]

                # Delete useless pages
                del pdf_content[page_number + 1 :]
                del ref_content[page_number + 1 :]
            break


def delete_non_printable_character(text: str) -> str:
    """
    Delete non printable characters from a text

    :param text: the text to clean

    :return: the cleaned text
    """
    return "".join([c for c in text if c.isprintable()])


def delete_redundant_content(pdf_content: List[List[str]]) -> List[List[str]]:
    """
    Delete redundant content from a PDF document and try to identify dynamic content wich is in great part redundant

    :param pdf_content: the content of the PDF document
    :return: the filtered content
    """
    first_page = pdf_content[0]
    delete_anchor: List[Tuple[int, int]] = []
    for line in first_page:
        for page in pdf_content[1:]:
            if first_page.index(line) == len(first_page) - 1:
                current_line = line.replace(" 1 ", f" {pdf_content.index(page) + 1} ")
            else:
                current_line = line
            if current_line in page:
                delete_anchor.append(
                    (pdf_content.index(page), page.index(current_line))
                )
            else:
                break

    for page_number, line_index in delete_anchor:
        del pdf_content[page_number][line_index]

    return pdf_content


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
