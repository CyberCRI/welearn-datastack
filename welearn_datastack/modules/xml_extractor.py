import logging
import re
from pathlib import Path
from typing import List

from welearn_datastack.data.xml_data import XMLData

logger = logging.getLogger(__name__)


class XMLExtractor:
    def __init__(self, xml_file_path_or_content: Path | str):
        """
        Initialize the XMLExtractor with the path or the content of XML file.
        :param xml_file_path_or_content: The path or the content of the XML file.
        """
        self.xml_file_path: Path | None

        match xml_file_path_or_content:
            case Path():
                logger.debug("Reading XML file from %s", xml_file_path_or_content)
                # If the input is a Path, read the content of the file
                self.xml_file_path = xml_file_path_or_content
                self.xml_raw_data = xml_file_path_or_content.open(mode="r").read()
            case str():
                logger.debug("Reading XML from raw data")
                # If the input is a string, store the raw data
                self.xml_file_path = None
                self.xml_raw_data = xml_file_path_or_content
            case _:
                raise ValueError("Invalid input type")

    def __str__(self):
        return self.xml_raw_data

    def __ge__(self, other):
        return self.xml_raw_data >= other.xml_raw_data

    def __gt__(self, other):
        return self.xml_raw_data > other.xml_raw_data

    def __le__(self, other):
        return self.xml_raw_data <= other.xml_raw_data

    def __lt__(self, other):
        return self.xml_raw_data < other.xml_raw_data

    def __eq__(self, other):
        return self.xml_raw_data == other.xml_raw_data

    def extract_content(self, tag: str) -> List[XMLData]:
        """
        Extract content and attributes of a specific tag from an XML file.
        :param tag: The tag to extract content and attributes from.

        :return: A list of XMLData containing the content and attributes of the tag.
        """

        # Pattern to capture the tag, its content and attributes
        pattern = rf"<{tag}([^>]*)>(.*?)</{tag}>"

        # Pattern to capture the attributes of the tag in the form of key="value"
        attr_pattern = re.compile(r'([\w:]+)="([^"]*)"')

        # Find all matches of the pattern in the XML raw data
        matches = re.findall(pattern, self.xml_raw_data, re.DOTALL)
        logger.info("Found %d matches for tag %s", len(matches), tag)

        ret = []
        for match in matches:
            attributes_string = match[0]  # Attributes
            content = match[1].strip()  # Content

            attributes = dict(attr_pattern.findall(attributes_string))
            ret.append(XMLData(content=content, attributes=attributes))
        return ret

    def extract_content_attribute_filter(
        self, tag: str, attribute_name: str, attribute_value: str | None = None
    ) -> List[XMLData]:
        """
        Extract content and attributes of a specific tag from an XML file.
        :param tag: The tag to extract content and attributes from.
        :param attribute_name: The name of the attribute to filter on.
        :param attribute_value: The value of the attribute to filter on, if None, only check for the existence of the attribute.
        :return:  A list of XMLData containing the content and attributes of the tag.
        """
        extracted = self.extract_content(tag)
        ret = []
        match attribute_value:
            case None:
                for data in extracted:
                    if attribute_name in data.attributes:
                        ret.append(data)
            case _:
                for data in extracted:
                    if data.attributes.get(attribute_name, None) == attribute_value:
                        ret.append(data)
        return ret
