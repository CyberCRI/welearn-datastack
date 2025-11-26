import json
import logging
from datetime import datetime
from functools import cache
from urllib.parse import urlparse, urlunparse

import requests.exceptions
import spacy
from pydantic import ValidationError
from requests import Session
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import AUTHORIZED_LICENSES
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.source_models.pressbooks import (
    PressBooksMetadataModel,
    PressBooksModel,
)
from welearn_datastack.exceptions import UnauthorizedLicense
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import clean_text

logger = logging.getLogger(__name__)

CONTAINERS_NAME = ["parts", "chapters", "front-matter", "back-matter"]


@cache
def _load_model():
    return spacy.load("xx_sent_ud_sm")


# Collector
class PressBooksCollector(IPluginRESTCollector):
    related_corpus = "press-books"

    @staticmethod
    def _create_pressbook_id(main_url: str, post_id: int):
        return f"{main_url}?p={post_id}"

    @staticmethod
    def _extract_book_main_url(url: str) -> str:

        parsed_url = urlparse(url)
        book_addr = urlunparse(
            ["https", parsed_url.netloc, parsed_url.path, "", "", ""]
        )

        return book_addr

    @staticmethod
    def _extract_post_id(url: str) -> str:
        parsed_url = urlparse(url)
        return parsed_url.query.replace("p=", "")

    @staticmethod
    def _extract_pressbook_type(url: str) -> str:
        http_client = get_new_https_session()
        ret = http_client.head(url, allow_redirects=True)
        ret.raise_for_status()

        p = urlparse(ret.url)
        type_name = p.path.split("/")[2]

        if type_name in ["chapter", "part"]:
            type_name += "s"

        return type_name

    @staticmethod
    def _extract_three_first_sentences(text: str) -> str:
        """
        Extracts the first three sentences from a given text.
        :param text: The input text from which to extract sentences.
        :return: A string containing the first three sentences.
        """
        nlp_model = _load_model()
        doc = nlp_model(text)
        sentences = [sent.text for sent in doc.sents]
        return " ".join(sentences[:3]) if len(sentences) >= 3 else text

    @staticmethod
    def _get_pressbook_document(client: Session, forged_url: str) -> PressBooksModel:
        post_content = client.get(url=forged_url)
        post_content.raise_for_status()
        raw_data = PressBooksModel.model_validate_json(json.dumps(post_content.json()))

        return raw_data

    @staticmethod
    def _get_pressbook_metadata(
        client: Session, forged_url: str
    ) -> PressBooksMetadataModel:
        metadata_resp = client.get(url=f"{forged_url}/metadata")
        metadata_resp.raise_for_status()
        raw_metadata = PressBooksMetadataModel.model_validate_json(
            json.dumps(metadata_resp.json())
        )
        return raw_metadata

    @staticmethod
    def _check_authorized_license(license_url: str) -> bool:
        if license_url in AUTHORIZED_LICENSES:
            return True
        raise UnauthorizedLicense(f"License {license_url} is not authorized")

    @staticmethod
    def extract_publisher(raw_metadata: PressBooksMetadataModel) -> str | None:
        """
        Extract publisher name from raw metadata.
        :param raw_metadata: The raw metadata object.
        :return: Publisher name or None if not available.
        """
        if raw_metadata.publisher:
            publisher = raw_metadata.publisher.name
        else:
            publisher = None
        return publisher

    @staticmethod
    def _extract_editors(raw_metadata: PressBooksMetadataModel) -> list[dict[str, str]]:
        """
        Extract editors from raw metadata.
        :param raw_metadata: The raw metadata object.
        :return: List of editors with their names.
        """
        editors: list[dict[str, str]] = []
        for editor in raw_metadata.editor:
            editors.append(
                {
                    "name": clean_text(editor.name),
                }
            )
        return editors

    @staticmethod
    def _extract_authors(raw_metadata: PressBooksMetadataModel) -> list[dict[str, str]]:
        """
        Extract authors from raw metadata.
        :param raw_metadata: The raw metadata object.
        :return: List of authors with their names and institutions.
        """
        authors: list[dict[str, str]] = []
        for author in raw_metadata.author:
            authors.append(
                {
                    "name": clean_text(author.name),
                    "misc": clean_text(author.contributor_institution),
                }
            )
        return authors

    @staticmethod
    def _extract_updated_date(
        main_url: str, post_id: str, raw_metadata: PressBooksMetadataModel
    ) -> float | None:
        """
        Extracts the updated date from raw metadata.
        :param main_url: The main URL of the book.
        :param post_id: The post ID.
        :param raw_metadata: The raw metadata object.
        :return: Updated date as a timestamp or None if not available.
        """
        if raw_metadata.modified_gmt:
            collected_update_date = raw_metadata.modified_gmt
            update_date = datetime.strptime(
                collected_update_date, "%Y-%m-%dT%H:%M:%S"
            ).timestamp()
        else:
            logger.warning(f"No update date found for post ID {post_id} in {main_url}")
            update_date = None
        return update_date

    @staticmethod
    def _extract_publication_date(
        main_url: str, post_id: str, raw_metadata: PressBooksMetadataModel
    ) -> float | None:
        """
        Extracts the publication date from raw metadata.
        :param main_url: The main URL of the book.
        :param post_id: The post ID.
        :param raw_metadata: The raw metadata object.
        :return: Publication date as a timestamp or None if not available.
        """
        if raw_metadata.date_gmt:
            collected_pubdate = raw_metadata.date_gmt
            pubdate = datetime.strptime(
                collected_pubdate, "%Y-%m-%dT%H:%M:%S"
            ).timestamp()
        elif raw_metadata.datePublished:
            # Fallback for datePublished
            collected_pubdate = raw_metadata.datePublished
            pubdate = datetime.strptime(collected_pubdate, "%Y-%m-%d").timestamp()
        else:
            logger.warning(
                f"No publication date found for post ID {post_id} in {main_url}"
            )
            pubdate = None
        return pubdate

    @staticmethod
    def _extract_content(raw_data: PressBooksModel) -> str:
        """
        Extracts and cleans the content from raw data.
        :param raw_data: The raw data object.
        :return: Cleaned content as a string.
        """
        not_formatted_content = raw_data.content.raw
        content = clean_text(not_formatted_content)
        return content

    @staticmethod
    def _compose_title(raw_metadata: PressBooksMetadataModel) -> str:
        """
        Composes the title from book title and element title.
        :param raw_metadata: The raw metadata object.
        :return: Composed title as a string.
        """
        book_title = clean_text(raw_metadata.isPartOf)
        element_title = clean_text(raw_metadata.name)

        if book_title:
            title = f"{book_title} - {element_title}"
        else:
            title = element_title
        return title

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        client = get_new_https_session()
        ret: list[WrapperRetrieveDocument] = []

        for document in documents:
            main_url = self._extract_book_main_url(document.url)
            post_id = self._extract_post_id(document.url)

            # Identify post type
            try:
                post_type = self._extract_pressbook_type(document.url)
            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving metadata for post ID {post_id} in {main_url}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue

            forged_url = f"{main_url}/wp-json/pressbooks/v2/{post_type}/{post_id}"

            try:
                raw_data = self._get_pressbook_document(client, forged_url)
            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving metadata for post ID {post_id} in {main_url}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue
            except ValidationError as e:
                msg = f"Error while parsing metadata for post ID {post_id} in {main_url}: {str(e)}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            try:
                raw_metadata = self._get_pressbook_metadata(client, forged_url)
            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving metadata for post ID {post_id} in {main_url}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue
            except ValidationError as e:
                msg = f"Error while parsing metadata for post ID {post_id} in {main_url}: {str(e)}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            try:
                self._check_authorized_license(raw_metadata.license.url)
            except UnauthorizedLicense:
                msg = f"Unauthorized license {raw_metadata.license.url} for post ID {post_id} in {main_url}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            title = self._compose_title(raw_metadata)

            # Content stuff
            content = self._extract_content(raw_data)

            # Date stuff
            pubdate = self._extract_publication_date(main_url, post_id, raw_metadata)
            update_date = self._extract_updated_date(main_url, post_id, raw_metadata)

            # Authors stuff
            authors = self._extract_authors(raw_metadata)

            # Editors stuff
            editors = self._extract_editors(raw_metadata)

            publisher = self.extract_publisher(raw_metadata)

            details = {
                "license": raw_metadata.license.url,
                "update_date": update_date,
                "publication_date": pubdate,
                "authors": authors,
                "editors": editors,
                "publisher": publisher,
                "type": post_type,
                "partOf": {"element": main_url, "order": None},
            }

            document.title = title
            document.full_content = content
            document.description = self._extract_three_first_sentences(content)
            document.details = details
            ret.append(WrapperRetrieveDocument(document=document))

        return ret
