import logging
import re
from html.parser import HTMLParser

from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore

logger = logging.getLogger(__name__)


class HTMLTagRemover(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, data):
        self.result.append(data)

    def get_text(self):
        return "".join(self.result)


def remove_extra_whitespace(text: str) -> str:
    """removes extra whitespace from text

    Args:
        text (str): text to evaluate

    Returns:
        str: text without extra whitespace
    """
    return " ".join(text.split())


def remove_html_tags(text: str) -> str:
    """
    removes html tags from text

    Args:
        text (str): text to evaluate

    Returns:
        str: text without html tags
    """
    remover = HTMLTagRemover()
    remover.feed(text + "\n")
    return remover.get_text()


def format_cc_license(license: str) -> str:
    """
    Format a Creative Commons license to a well formated url.
    :param license: License to format.
    :return: License well formated.
    """
    splitted_elements = license.split("-")
    version = splitted_elements[-1].strip()
    rights_code = "-".join(splitted_elements[1:-1]).strip().lower()

    return (
        f"https://creativecommons.org/licenses/{rights_code.lower()}/{version.lower()}/"
    )


def clean_text_keep_punctuation(text):
    # Remplace les retours à la ligne et autres espaces spéciaux par un espace
    text = re.sub(r"\s+", " ", text)
    # Conserve lettres, chiffres, ponctuation de base et espace
    text = re.sub(r'[^a-zA-Z0-9\s.,!?;:\'"\-()]', "", text)
    return text.strip()


def get_url_license_from_dc_format(soup: BeautifulSoup) -> str:
    """
    Extract the license of the document from the DC.rights meta tag.
    :param soup: BeautifulSoup object of the document.
    :return: License of the document well formated.
    """
    soup_license = soup.find("meta", {"name": "DC.rights"})
    license = soup_license["content"]  # type: ignore

    en_license_name = "OpenEdition Books License".lower().split()
    fr_license_name = "Licence OpenEdition Books".lower().split()
    en_license_name.sort()
    fr_license_name.sort()
    other_known_licenses = [en_license_name, fr_license_name]

    license_split_n_sort = license.lower().split()  # type: ignore
    license_split_n_sort.sort()

    if license.startswith("Creative Commons"):  # type: ignore
        # It's a CC license
        full_cc_code = license.split(" - ")[-1].strip()  # type: ignore
        rights_code = full_cc_code.split(" ")[1].strip()
        version = full_cc_code.split(" ")[2].strip()
        well_formated_license = f"https://creativecommons.org/licenses/{rights_code.lower()}/{version.lower()}/"
        return well_formated_license
    elif license_split_n_sort in other_known_licenses:
        return "https://www.openedition.org/12554"
    return license  # type: ignore


def extract_property_from_html(
    soup_find: Tag | NavigableString | None,
    mandatory: bool = True,
    error_property_name: str | None = None,
    attribute_name="content",
) -> str:
    """
    Extract the text from a BeautifulSoup object

    Args:
        soup_find (Tag | NavigableString | None): BeautifulSoup object
        mandatory (bool, optional): If the property is mandatory. Defaults to True.
        error_property_name (str | None, optional): Name of the property. Defaults to None.
        attribute_name (str, optional): Name of the attribute to extract. Defaults to "content".
    Returns:
        str: The extracted text from the BeautifulSoup object
    """
    match soup_find:
        case Tag():
            if attribute_name in soup_find.attrs:
                content = soup_find[attribute_name]
                if isinstance(content, list):
                    return content[0].strip()
                return content.strip()
            return soup_find.text.strip()
        case NavigableString():
            return str(soup_find).strip()
        case _:
            if mandatory:
                error_property_name = error_property_name or "Property"
                raise ValueError(f"{error_property_name} not found")
            return ""


def clean_return_to_line(string: str):
    ret = re.sub(r"([\n\t\r])", "", string).strip()
    return ret


def clean_text(content: str) -> str:
    """
    Clean the content of a document by removing html tags and extra whitespace

    Args:
        content (str): the content of the document

    Returns:
        str: the cleaned content
    """
    return remove_extra_whitespace(remove_html_tags(content)).strip()


def get_url_without_hal_like_versionning(url: str) -> str:
    """
    Get the URL without the versionning part
    https://hal.science/hal-04337383v1 -> https://hal.science/hal-04337383
    :param json_dict: JSON dict from HAL API
    :return: URL without versionning
    """
    # Get the URL without the versionning part
    uri = re.sub(r"v\d+$", "", url)
    return uri.strip()
