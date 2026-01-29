import io
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from itertools import batched
from typing import Iterable
from urllib.parse import urlparse

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import (
    AUTHORIZED_LICENSES,
    HEADERS,
    HTTPS_CREATIVE_COMMONS,
    OPEN_ALEX_BASE_URL,
    PUBLISHERS_TO_AVOID,
    YEAR_FIRST_DATE_FORMAT,
)
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.topics import TopicDetails
from welearn_datastack.data.source_models.open_alex import (
    Location,
    OpenAlexModel,
    OpenAlexResult,
    Topic,
)
from welearn_datastack.exceptions import (
    ClosedAccessContent,
    ManagementExceptions,
    NotEnoughData,
    PDFFileSizeExceedLimit,
    UnauthorizedLicense,
    UnauthorizedPublisher,
    UnknownURL,
)
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    extract_txt_from_pdf_with_tika,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import remove_extra_whitespace

logger = logging.getLogger(__name__)


class OpenAlexCollector(IPluginRESTCollector):
    related_corpus = "openalex"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))
        self.pdf_size_file_limit: int = int(os.getenv("PDF_SIZE_FILE_LIMIT", 2000000))
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")

        team_email = os.getenv("TEAM_EMAIL")
        if not isinstance(team_email, str):
            raise ValueError("Please define TEAM_EMAIL in environment variable")
        self.team_email = team_email

    @staticmethod
    def _invert_abstract(inv_index: dict[str, list[int]]) -> str:
        if inv_index is not None:
            l_inv = [(w, p) for w, pos in inv_index.items() for p in pos]
            return " ".join(map(lambda x: x[0], sorted(l_inv, key=lambda x: x[1])))

    @staticmethod
    def _extract_openalex_id_from_urls(urls: Iterable[str]) -> list[str]:
        openalex_ids = []
        for url in urls:
            if url is None:
                logger.warning("URL is None, skip it")
                continue
            parsed_url = urlparse(url)
            if parsed_url.hostname and parsed_url.hostname.lower() == "openalex.org":
                openalex_ids.append(parsed_url.path.lstrip("/"))
            else:
                raise UnknownURL(
                    f"URL {url} does not have the expected hostname 'openalex.org' - expected format: https://openalex.org/<id>"
                )

        if len(openalex_ids) == 0:
            raise NotEnoughData("No valid OpenAlex IDs found in the provided URLs")

        return openalex_ids

    def _generate_api_query_params(
        self, urls: list[str], page_ln: int
    ) -> dict[str, str | bool | int]:
        return {
            "filter": f"ids.openalex:{'|'.join(urls)}",
            "per_page": page_ln,
            "mailto": self.team_email,
            "select": "title,ids,language,abstract_inverted_index,publication_date,authorships,open_access,best_oa_location,publication_date,type,topics,keywords,referenced_works,related_works,locations",
        }

    def _get_pdf_content(self, url: str, file_size_limit: int | None = None) -> str:
        logger.info("Getting PDF content from %s", url)
        client = get_new_https_session(retry_total=0)

        if file_size_limit and file_size_limit < 0:
            raise ValueError(f"file_size_limit must be positive : {file_size_limit}")

        if file_size_limit:
            resp_head = client.head(
                url, headers=HEADERS, allow_redirects=True, timeout=30
            )
            try:
                content_length = int(resp_head.headers.get("content-length"))
                logger.info(f"PDF size is {content_length}")
            except ValueError:
                raise ValueError(f"Cannot retrieved this pdf size : {url}")

            if content_length > file_size_limit:
                raise PDFFileSizeExceedLimit(
                    f"File size is {content_length} and limit is {file_size_limit}"
                )

        response = client.get(url, headers=HEADERS, timeout=300)
        response.raise_for_status()

        with io.BytesIO(response.content) as pdf_file:
            pdf_content = extract_txt_from_pdf_with_tika(
                pdf_content=pdf_file, tika_base_url=self.tika_address
            )

            # Delete non printable characters
            pdf_content = [
                [delete_non_printable_character(word) for word in page]
                for page in pdf_content
            ]

            pages = []
            for content in pdf_content:
                page_text = " ".join(content)
                page_text = replace_ligatures(page_text)
                page_text = remove_hyphens(page_text)
                page_text = delete_accents(page_text)

                pages.append(page_text)
            ret = remove_extra_whitespace(" ".join(pages))

        return ret

    @staticmethod
    def _transform_topics(topics: list[Topic]) -> list[TopicDetails]:
        """
        Transform the topics from the original json to the format expected by the WeLearn DB
        :param topics: Original json from OpenAlex
        :return: list of topics in the format expected by the WeLearn DB
        """
        transformed = []
        unique_items = set()  # For check every external_id is unique

        for topic in topics:
            domain = topic.domain
            field = topic.field
            subfield = topic.subfield

            # Hierachical level definition
            levels = [
                (domain.model_dump(), 0, "domain", []),
                (field.model_dump(), 1, "field", [domain.id]),
                (subfield.model_dump(), 2, "subfield", [field.id]),
                (
                    {"id": topic.id, "display_name": topic.display_name},
                    3,
                    "topic",
                    [subfield.id],
                ),
            ]

            # Avoid duplicate
            for item, depth, depth_name, parent_ids in levels:
                external_id = item["id"]
                if external_id not in unique_items:
                    unique_items.add(external_id)
                    transformed.append(
                        TopicDetails(
                            external_id=external_id,
                            name=item["display_name"],
                            depth=depth,
                            external_depth_name=depth_name,
                            directly_contained_in=parent_ids,
                        )
                    )

        return transformed

    def _remove_useless_first_word(
        self, string_to_clear: str, useless_words: list[str]
    ):
        """
        Remove the first word of a string
        :param string_to_clear: String to clear of useless words
        :param useless_words: Words we want to eliminate from the string
        :return: string cleaned
        """
        if len(string_to_clear) <= 0:
            return ""

        useless_words_lowered = [word.lower() for word in useless_words]
        string_to_clear_splited = string_to_clear.split()

        # If the two first words start with a capital letter
        two_capitals_flag = (
            string_to_clear_splited[0][0].isupper()
            and string_to_clear_splited[1][0].isupper()
        )

        if (
            two_capitals_flag
            and string_to_clear_splited[0].lower() in useless_words_lowered
        ):
            try:
                return self._remove_useless_first_word(
                    " ".join(string_to_clear_splited[1:]), useless_words
                )
            except IndexError:
                logger.error(f"This string can't be cleaned :{string_to_clear}")
        return string_to_clear

    def _update_welearn_document(self, wrapper: WrapperRawData) -> WeLearnDocument:
        document_title = wrapper.raw_data.title
        document_url = wrapper.raw_data.ids.openalex
        logger.info(f"Process {document_url}...")
        document_desc = self._remove_useless_first_word(
            string_to_clear=self._invert_abstract(
                wrapper.raw_data.abstract_inverted_index
            ),
            useless_words=["background", "abstract", "introduction"],
        )

        work_locations: list[Location] = wrapper.raw_data.locations
        host_ids = []
        for location in work_locations:
            host_organization_lineage_malformed: list[str] = (
                location.source.host_organization_lineage
            )
            if (
                host_organization_lineage_malformed is None
                or len(host_organization_lineage_malformed) == 0
            ):
                continue
            try:
                host_organization_lineage = self._extract_openalex_id_from_urls(
                    host_organization_lineage_malformed
                )
                host_ids.extend(host_organization_lineage)
            except ManagementExceptions as e:
                logger.warning(
                    f"Cannot extract host organization lineage from {location.source.host_organization_lineage}: {e}"
                )
                continue

        avoiding_ids = PUBLISHERS_TO_AVOID
        for host_id in host_ids:
            if host_id.upper() in avoiding_ids:
                raise UnauthorizedPublisher(f"{host_id} is not authorized in welearn")

        document_content = document_desc
        if wrapper.raw_data.best_oa_location.pdf_url is None:
            pdf_flag = False
        else:
            try:
                # Get the content of the PDF
                logger.info(
                    f"Getting PDF content from {wrapper.raw_data.best_oa_location.pdf_url}"
                )
                document_content = self._get_pdf_content(
                    wrapper.raw_data.best_oa_location.pdf_url,
                    file_size_limit=self.pdf_size_file_limit,
                )
                pdf_flag = True
            except Exception as e:
                logger.exception(
                    f"PDF retrievement error, use description as content: {e}"
                )
                pdf_flag = False

        publication_date = int(
            datetime.strptime(
                wrapper.raw_data.publication_date, YEAR_FIRST_DATE_FORMAT
            ).timestamp()
        )

        authors = []
        for author_info in wrapper.raw_data.authorships:
            authors.append(
                {
                    "name": author_info.author.display_name,
                    "misc": ",".join(author_info.raw_affiliation_strings),
                }
            )

        if not wrapper.raw_data.open_access.is_oa:
            raise ClosedAccessContent()
        else:
            logger.info(f"The content {document_url} is open access")

        best_oa_location_info = wrapper.raw_data.best_oa_location

        # Open Alex format is cc-by...
        license_openalex_format: str = best_oa_location_info.license

        if not license_openalex_format.startswith("cc"):
            raise UnauthorizedLicense()

        logger.info(f"The content {document_url} is legally usable")

        license_good_format = f"{HTTPS_CREATIVE_COMMONS}/licenses/{license_openalex_format.replace('cc-', '')}/4.0/"

        if license_good_format.lower() not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(f"{license_good_format.lower()} is not allowed")

        logger.info(f"The content {document_url} is legally usable")

        document_details = {
            "publication_date": publication_date,
            "type": wrapper.raw_data.type,
            "doi": wrapper.raw_data.ids.doi,
            "publisher": wrapper.raw_data.best_oa_location.source.host_organization_name,
            "license_url": license_good_format,
            "issn": wrapper.raw_data.best_oa_location.source.issn_l,
            "content_from_pdf": pdf_flag,
            "topics": [
                asdict(t) for t in self._transform_topics(wrapper.raw_data.topics)
            ],
            "tags": [x.display_name for x in wrapper.raw_data.keywords],
            "referenced_works": wrapper.raw_data.referenced_works,
            "related_works": wrapper.raw_data.related_works,
            "authors": authors,
        }
        wrapper.document.title = document_title
        wrapper.document.description = document_desc
        wrapper.document.content = document_content
        wrapper.document.details = document_details
        return wrapper.document

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        ret: list[WrapperRetrieveDocument] = []
        page_length = 50
        sub_batches: batched[WeLearnDocument] = batched(documents, page_length)
        http_client = get_new_https_session()

        for sub_batch in sub_batches:
            urls_docs = {d.url: d for d in sub_batch}
            try:
                local_params = self._generate_api_query_params(
                    urls=self._extract_openalex_id_from_urls(urls_docs.keys()),
                    page_ln=page_length,
                )
                ret_from_openalex = http_client.get(
                    url=OPEN_ALEX_BASE_URL, params=local_params
                )
                ret_from_openalex.raise_for_status()

                # Compare returned list of urls from OpenAlex and the requested ones
                oa_resp = OpenAlexModel.model_validate_json(
                    json.dumps(ret_from_openalex.json())
                )
                oa_results: list[OpenAlexResult] = oa_resp.results
                urls_from_open_alex = [result.ids.openalex for result in oa_results]
                not_returned_urls = [
                    url for url in urls_docs.keys() if url not in urls_from_open_alex
                ]
                logger.info(f"There is {len(not_returned_urls)} not returned urls")
                for not_returned_url in not_returned_urls:
                    ret.append(
                        WrapperRetrieveDocument(
                            document=urls_docs[not_returned_url],
                            error_info=f"{not_returned_url} is not returned from openalex API",
                        )
                    )

                for result in oa_results:
                    wrapper = WrapperRawData(
                        document=urls_docs[result.ids.openalex], raw_data=result
                    )
                    try:
                        doc = self._update_welearn_document(wrapper)
                        ret.append(WrapperRetrieveDocument(document=doc))
                    except Exception as e:
                        logger.exception(
                            f"Error while trying to get contents this url : {result.ids.openalex}",
                            e,
                        )
                        ret.append(
                            WrapperRetrieveDocument(
                                document=urls_docs[result.ids.openalex],
                                error_info=str(e),
                            )
                        )
            except Exception as e:
                logger.exception(
                    f"Error while trying to get contents from a sub batch urls: {e}",
                )
                for doc in sub_batch:
                    ret.append(
                        WrapperRetrieveDocument(
                            document=doc,
                            http_error_code=get_http_code_from_exception(e),
                            error_info=f"Error while trying to get contents from OpenAlex API: {str(e)}",
                        )
                    )
                continue

        return ret
