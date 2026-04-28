import io
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from itertools import batched
from typing import Any, Iterable
from urllib.parse import urlparse

from welearn_database.data.enumeration import ExternalIdType
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
    get_pdf_content,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.modules.url_utils import extract_doi_number
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
    def _invert_abstract(inv_index: dict[str, list[int]]) -> str | None:
        if inv_index is not None:
            l_inv = [(w, p) for w, pos in inv_index.items() for p in pos]
            return " ".join([x[0] for x in sorted(l_inv, key=lambda x: x[1])])
        return None

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
        document_url = wrapper.raw_data.ids.openalex
        logger.info(f"Process {document_url}...")
        self._check_publisher_authorization(wrapper)
        self._check_access(document_url, wrapper)
        self._check_license(document_url, wrapper)
        logger.info(f"The content {document_url} is legally usable")

        document_desc = self.build_description(wrapper)
        document_content, pdf_flag = self._resolve_full_content(document_desc, wrapper)
        document_details = self._build_details(document_url, pdf_flag, wrapper)
        wrapper.document.title = wrapper.raw_data.title
        wrapper.document.description = document_desc
        wrapper.document.content = document_content
        wrapper.document.details = document_details
        wrapper.document.external_id = self._get_doi(wrapper)
        wrapper.document.external_id_type = ExternalIdType.DOI

        return wrapper.document

    def _build_details(
        self,
        document_url: str | None,
        pdf_flag: str | Any,
        wrapper: WrapperRawData,
    ) -> dict[
        str | Any,
        int | str | None | list[dict[str, Any]] | list[str | None] | list[str] | Any,
    ]:
        """
        Build the details of the document in a dict format expected by the WeLearn DB
        :param document_url: URL of the document to build the details for (used for logging purposes)
        :param pdf_flag: flag indicating if the content of the document is from the PDF or not (used for logging purposes)
        :param wrapper: WrapperRawData containing the raw data of the document to build the details from
        :return: dict containing the details of the document in the format expected by the WeLearn DB
        """
        document_details = {
            "publication_date": self._build_publication_date(wrapper),
            "type": wrapper.raw_data.type,
            "doi": self._get_doi(wrapper),
            "publisher": wrapper.raw_data.best_oa_location.source.host_organization_name,
            "license_url": self._get_licence(document_url, wrapper),
            "issn": wrapper.raw_data.best_oa_location.source.issn_l,
            "content_from_pdf": pdf_flag,
            "topics": [
                asdict(t) for t in self._transform_topics(wrapper.raw_data.topics)
            ],
            "tags": [x.display_name for x in wrapper.raw_data.keywords],
            "referenced_works": wrapper.raw_data.referenced_works,
            "related_works": wrapper.raw_data.related_works,
            "authors": self._build_authors_list(wrapper),
        }
        return document_details

    @staticmethod
    def _get_doi(wrapper: WrapperRawData) -> str | None:
        doi = wrapper.raw_data.ids.doi
        if doi.startswith("https://doi.org/"):
            doi = extract_doi_number(doi)
        return doi

    @staticmethod
    def _build_authors_list(wrapper: WrapperRawData) -> list[Any]:
        authors = []
        for author_info in wrapper.raw_data.authorships:
            authors.append(
                {
                    "name": author_info.author.display_name,
                    "misc": ",".join(author_info.raw_affiliation_strings),
                }
            )
        return authors

    @staticmethod
    def _build_publication_date(wrapper: WrapperRawData) -> int:
        publication_date = int(
            datetime.strptime(
                wrapper.raw_data.publication_date, YEAR_FIRST_DATE_FORMAT
            ).timestamp()
        )
        return publication_date

    def _resolve_full_content(
        self, document_desc: str | Any, wrapper: WrapperRawData
    ) -> tuple[bool, str | Any]:
        """
        Get the full content of the document. If the PDF is available and can be retrieved, extract the content from the PDF. Otherwise, use the description as the content.
        :param document_desc: Description of the document to use as content if the PDF is not available or cannot be retrieved
        :param wrapper: WrapperRawData containing the raw data of the document to get the content from
        :return: tuple containing a flag indicating if the content is from the PDF and the content of the document
        """
        document_content = document_desc

        if wrapper.raw_data.best_oa_location.pdf_url is None:
            pdf_flag = False
        else:
            try:
                # Get the content of the PDF
                logger.info(
                    f"Getting PDF content from {wrapper.raw_data.best_oa_location.pdf_url}"
                )
                document_content = get_pdf_content(
                    pdf_url=wrapper.raw_data.best_oa_location.pdf_url,
                    pdf_size_file_limit=self.pdf_size_file_limit,
                    tika_address=self.tika_address,
                )
                pdf_flag = True
            except Exception as e:
                logger.exception(
                    f"PDF retrievement error, use description as content: {e}"
                )
                pdf_flag = False
        return document_content, pdf_flag

    def build_description(self, wrapper: WrapperRawData) -> str | Any:
        document_desc = self._remove_useless_first_word(
            string_to_clear=self._invert_abstract(
                wrapper.raw_data.abstract_inverted_index
            ),
            useless_words=["background", "abstract", "introduction"],
        )
        return document_desc

    @staticmethod
    def _check_access(document_url: str, wrapper: WrapperRawData):
        """
        Check if the document is open access. If not, raise a ClosedAccessContent exception
        :param document_url: URL of the document to check
        :param wrapper: WrapperRawData containing the raw data of the document to check
        :exception ClosedAccessContent: If the document is not open access
        """
        if not wrapper.raw_data.open_access.is_oa:
            raise ClosedAccessContent()
        else:
            logger.info(f"The content {document_url} is open access")

    def _check_license(self, document_url: str, wrapper: WrapperRawData):
        """
        Check if the license of the document is in the list of authorized licenses. If not, raise an UnauthorizedLicense exception
        :param document_url: URL of the document to check
        :param wrapper: WrapperRawData containing the raw data of the document to check
        :exception UnauthorizedLicense: If the license of the document is not in the list of authorized licenses
        """
        license_good_format = self._get_licence(document_url, wrapper)

        if license_good_format.lower() not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(f"{license_good_format.lower()} is not allowed")

    @staticmethod
    def _get_licence(document_url: str | None, wrapper: WrapperRawData) -> str:
        """
        Get the license of the document in a good format (https://creativecommons.org/licenses/xxx/4.0/) from the raw data of the document. If the license is not in the expected format, log a warning and return it in lowercase.
        :param document_url: URL of the document to get the license from (used for logging purposes)
        :param wrapper: WrapperRawData containing the raw data of the document to get the license from
        :return: License of the document in a good format (https://creativecommons.org/licenses/xxx/4.0/) if it is in the expected format, otherwise in lowercase
        """
        best_oa_location_info = wrapper.raw_data.best_oa_location
        license_openalex_format: str = best_oa_location_info.license
        if license_openalex_format is None:
            logger.warning(
                f"No license found for {document_url}, set it to empty string"
            )
            return ""

        if not license_openalex_format.startswith("cc-"):
            logger.warning(
                f"License {license_openalex_format} of {document_url} is not in the expected format, set it to lowercase"
            )
            return license_openalex_format.lower()

        license_good_format = f"{HTTPS_CREATIVE_COMMONS}/licenses/{license_openalex_format.replace('cc-', '')}/4.0/"
        return license_good_format

    def _check_publisher_authorization(self, wrapper: WrapperRawData):
        """
        Check if the publisher of the document is authorized to be used in WeLearn. If not, raise an UnauthorizedPublisher exception

        :param wrapper: WrapperRawData containing the raw data of the document to check
        :exception UnauthorizedPublisher: If the publisher is not authorized to be used in WeLearn
        """
        work_locations: list[Location] = wrapper.raw_data.locations
        host_ids = self.get_host_ids(work_locations)

        avoiding_ids = PUBLISHERS_TO_AVOID
        for host_id in host_ids:
            if host_id.upper() in avoiding_ids:
                raise UnauthorizedPublisher(f"{host_id} is not authorized in welearn")

    def get_host_ids(self, work_locations: list[Location]) -> list[Any]:
        """
        Get the host organization lineage from the work locations and extract the OpenAlex IDs from it. If the host organization lineage is not in the expected format, log a warning and skip it.

        :param work_locations: list of Location objects containing the host organization lineage to extract the OpenAlex IDs from
        :return: list of OpenAlex IDs extracted from the host organization lineage
        """
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
        return host_ids

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
