import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup  # type: ignore
from requests import Session  # type: ignore
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import AUTHORIZED_LICENSES, MD_OE_BOOKS_BASE_URL
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import ClosedAccessContent
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import extract_property_from_html

logger = logging.getLogger(__name__)


class OpenEditionBooksCollector(IPluginScrapeCollector):
    related_corpus = "open-edition-books"

    def __init__(self) -> None:
        super().__init__()
        self.timeout = int(os.environ.get("SCRAPING_TIMEOUT", 60))

        self.parent_page_cache: Dict[str, BeautifulSoup] = {}

    def _scrape_url(self, document: WeLearnDocument) -> WeLearnDocument:
        """
        Scrape an document
        :param document: Document to scrape
        :return: WrapperRetrieveDocument
        """
        logger.info("Scraping url : '%s'", document.url)
        https_session = get_new_https_session()

        md_id, mets_api_res = self._get_mets_metadata(https_session, document.url)
        dmdid = f"MD_OB_{md_id.replace('/', '_')}"

        resource_type = ""
        title = None
        desc = None

        # Root extractor is the full XML file from the METS api, it's opposed to the
        # local_dmd which is the XML file of the chapter
        root_extractor: XMLExtractor | None = None

        soup: BeautifulSoup | None = None
        if mets_api_res.status_code == 200:
            root_extractor = XMLExtractor(mets_api_res.content.decode("utf-8"))
            dmd = root_extractor.extract_content_attribute_filter(
                "mets:dmdSec", "ID", dmdid
            )
            try:
                dmd_extractor = XMLExtractor(dmd[0].content)
                resource_type = dmd_extractor.extract_content("dcterms:type")[0].content
            except IndexError:
                raise ValueError(
                    "The DMD section related to DMDID was not found %s on %s",
                    dmdid,
                    document.url,
                )
        elif mets_api_res.status_code == 404:
            soup = self._get_soup_from_url(https_session, document.url)

            # Get type
            resource_type = extract_property_from_html(
                soup.find("meta", {"name": "DC.type"})
            )
            if resource_type == "BookSection":
                resource_type = "chapter"
        else:
            mets_api_res.raise_for_status()  # Raise exception if status code is not a good one

        details: Dict[str, Any] = {"partOf": []}

        content = ""

        match resource_type.lower():
            case "book":
                details["type"] = "book"
                if not root_extractor:
                    logger.warning("Weird case, cannot accessed to API before :%s", url)
                    md_id, mets_api_res = self._get_mets_metadata(https_session, url)
                    root_extractor = XMLExtractor(mets_api_res.content.decode("utf-8"))

                if not self._is_open_access(root_extractor):
                    logger.exception("Access rights not open access")
                    raise ClosedAccessContent("Access rights not open access")

                book_dmd = self._extract_book_dmd_id(root_extractor)
                desc_lang = book_dmd.extract_content_attribute_filter(
                    tag="dcterms:language",
                    attribute_name="xsi:type",
                    attribute_value="dcterms:RFC1766",
                )[0].content
                current_license = self._get_current_license(book_dmd)
                details["license"] = current_license

                desc = self._get_description(book_dmd, desc_lang)
                content = desc
                title = book_dmd.extract_content("dcterms:title")[0].content

                # Authors
                authors = self._get_authors(book_dmd)
                details["authors"] = authors

                # Identifiers DOI and ISBN
                doi, isbn = self._get_doi_and_isbn(book_dmd)
                details["doi"] = doi
                details["isbn"] = isbn

            case "chapter":
                details["type"] = "chapter"
                if not soup:
                    soup = self._get_soup_from_url(https_session, document.url)

                parent_url = extract_property_from_html(
                    soup.find("link", {"rel": "Contents"}), attribute_name="href"
                )
                md_id, mets_api_res = self._get_mets_metadata(https_session, parent_url)
                root_extractor = XMLExtractor(mets_api_res.content.decode("utf-8"))

                if not self._is_open_access(root_extractor):
                    logger.exception("Access rights not open access")
                    raise ClosedAccessContent("Access rights not open access")

                dmds = root_extractor.extract_content("mets:dmdSec")

                # Local dmd is the XML file of the chapter
                local_dmd: XMLExtractor | None = None
                dmds.sort(key=lambda x: x.attributes["ID"])

                order_i = 0
                for d in dmds:
                    # Count the order of chapters and doesn't care about other types
                    dmd_extractor = XMLExtractor(d.content)
                    if (
                        dmd_extractor.extract_content("dcterms:type")[0].content
                        == "chapter"
                    ):
                        if d.attributes["ID"] == dmdid:
                            local_dmd = dmd_extractor
                            details["partOf"].append(
                                {"element": parent_url, "order": order_i}
                            )
                            order_i += 1

                            break

                if not local_dmd:
                    raise ValueError(
                        f"The DMD section related to DMDID was not found {dmdid} on {document.url}",
                    )

                # Get DOI and ISBN
                doi, isbn = self._get_doi_and_isbn(local_dmd)
                details["doi"] = doi
                details["isbn"] = isbn

                # Get title
                book_title = root_extractor.extract_content("dcterms:title")[0].content
                chapter_title = local_dmd.extract_content("dcterms:title")[0].content
                title = f"{book_title} - {chapter_title}"

                # Get authors
                authors = self._get_authors(local_dmd)
                details["authors"] = authors

                # Get language
                desc_lang = local_dmd.extract_content_attribute_filter(
                    tag="dcterms:language",
                    attribute_name="xsi:type",
                    attribute_value="dcterms:RFC1766",
                )[0].content

                # Get license
                current_license = self._get_current_license(local_dmd).lower().strip()
                details["license"] = current_license

                access_rights = (
                    local_dmd.extract_content("dcterms:accessRights")[0]
                    .content.lower()
                    .split("/")[-1]
                    .strip()
                )

                # Get description
                desc = self._get_description(local_dmd, desc_lang)

                # Get content
                is_open_access = access_rights == "openaccess"
                if not is_open_access:
                    logger.warning("Access rights not open access: %s", access_rights)

                if current_license not in AUTHORIZED_LICENSES:
                    logger.warning("License not recognized: %s", current_license)

                if not is_open_access or current_license not in AUTHORIZED_LICENSES:
                    logger.warning(
                        "Chapter not scraped, access rights: %s, license: %s",
                        access_rights,
                        current_license,
                    )
                    content = desc
                else:
                    # Delete span
                    for span in soup.find_all("span"):
                        span.decompose()

                    # Delete a
                    for a in soup.find_all("a"):
                        a.decompose()

                    anchor_fulltext = soup.find("div", {"id": "anchor-fulltext"})
                    if not anchor_fulltext:
                        raise ValueError(
                            "No anchor-fulltext found, so no content can be scraped"
                        )

                    content = anchor_fulltext.get_text(separator="\n ").strip()

            case _:
                raise ValueError(f"Resource type not recognized: {resource_type}")
        # Universal metadata

        # Tags from tag "citation_keywords"
        tags = root_extractor.extract_content_attribute_filter(
            "dcterms:subject", "xml:lang", desc_lang
        )
        details["tags"] = [tag.content.lower().strip() for tag in tags]

        # Get publication date
        publication_date_str = root_extractor.extract_content("dcterms:issued")[
            0
        ].content
        publication_date_ts = datetime.strptime(
            publication_date_str, "%Y-%m-%dT%H:%M:%S%z"
        ).timestamp()
        details["publication_date"] = int(publication_date_ts)

        # Get publisher name
        publisher = root_extractor.extract_content("dcterms:publisher")[0].content
        details["publisher"] = publisher

        if not title:
            raise ValueError("No title found")

        if not desc:
            raise ValueError("No description found")

        document.title = title
        document.description = desc
        document.full_content = content
        document.details = details

        return document

    @staticmethod
    def _extract_book_dmd_id(xml_extractor):
        dmds = xml_extractor.extract_content("mets:dmdSec")
        for dmd in dmds:
            dmd_extractor = XMLExtractor(dmd.content)
            if dmd_extractor.extract_content("dcterms:type")[0].content == "book":
                return dmd_extractor
        raise ValueError("No book DMD section found")

    @staticmethod
    def _get_doi_and_isbn(xml_extractor):
        doi = ""
        isbn = ""
        urn_doi = xml_extractor.extract_content_attribute_filter(
            tag="dcterms:identifier", attribute_name="scheme", attribute_value="URN"
        )
        for urn in urn_doi:
            if urn.content.startswith("urn:doi:"):
                doi = urn.content.replace("urn:doi:", "")
            elif urn.content.startswith("urn:isbn:"):
                isbn = urn.content.replace("urn:isbn:", "")
        return doi, isbn

    @staticmethod
    def _get_authors(xml_extractor):
        ret = []
        authors = xml_extractor.extract_content("dcterms:creator")
        for author in authors:
            firstname = author.content.split(",")[1].strip()
            lastname = author.content.split(",")[0].strip()
            fullname = f"{firstname} {lastname}"
            ret.append({"name": fullname, "misc": ""})
        return ret

    @staticmethod
    def _get_current_license(root_extractor):
        current_license = root_extractor.extract_content(tag="dcterms:rights")[
            0
        ].content
        return current_license

    @staticmethod
    def _get_description(root_extractor, lang):
        # Retrieve abstract for the language of the document
        try:
            desc = root_extractor.extract_content_attribute_filter(
                tag="dcterms:abstract",
                attribute_name="xml:lang",
                attribute_value=lang,
            )[0].content
        except IndexError:
            logger.info("No abstract, switch to description")
            desc = root_extractor.extract_content(
                tag="dcterms:description",
            )[0].content

        return desc

    @staticmethod
    def _is_open_access(xml: XMLExtractor):
        access_rights = xml.extract_content("dcterms:accessRights")
        if len(access_rights) == 0:
            logger.warning("No access rights found")
            return False
        for access in access_rights:
            try:
                if access.content.lower().split("/")[-1].strip() != "openaccess":
                    return False
            except IndexError:
                return False
        return True

    def _get_soup_from_url(self, https_session: Session, url: str):
        """
        Get the soup from the url
        :param https_session:  The https session
        :param url:  The url of the book to scrape
        :return:  The soup of the page
        """
        req_res = https_session.get(url=url, timeout=self.timeout)
        req_res.raise_for_status()  # Raise exception if status code is not a good one
        txt = req_res.text
        soup = BeautifulSoup(txt, "html.parser")
        return soup

    def _get_mets_metadata(self, https_session, url):
        """
        Get the METS metadata from the API
        :param https_session:  The https session
        :param url:  The url of the book
        :return: The md_id and the response of the API
        """
        md_id = url.replace("https://books.openedition.org/", "")
        md_url = MD_OE_BOOKS_BASE_URL.replace("<md_id>", md_id)
        mets_api_res = https_session.get(url=md_url, timeout=self.timeout)
        return md_id, mets_api_res

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running OpenEditionBooksCollector plugin")
        ret: List[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                ret.append(
                    WrapperRetrieveDocument(
                        document=self._scrape_url(document),
                    )
                )
            except Exception as e:
                msg = f"Error while scraping url,\n url: '{document.url}' \nError: {str(e)}"
                logger.exception(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                        http_error_code=get_http_code_from_exception(e),
                    )
                )
                continue

        logger.info(
            "OpenEditionBooksCollector plugin finished, %s urls scraped", len(ret)
        )
        return ret
