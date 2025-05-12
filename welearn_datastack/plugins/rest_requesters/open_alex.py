import io
import logging
import os
from datetime import datetime
from itertools import batched
from typing import Any, Dict, List, Tuple

from langdetect import detect
from pypdf import PdfReader

from welearn_datastack.constants import (
    AUTHORIZED_LICENSES,
    HEADERS,
    HTTPS_CREATIVE_COMMONS,
    OPEN_ALEX_BASE_URL,
    YEAR_FIRST_DATE_FORMAT,
)
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import (
    ClosedAccessContent,
    PDFFileSizeExceedLimit,
    PDFPagesSizeExceedLimit,
    UnauthorizedLicense,
)
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    extract_txt_from_pdf,
    large_pages_size_flag,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import remove_extra_whitespace
from welearn_datastack.utils_.text_stat_utils import (
    predict_duration,
    predict_readability,
)

logger = logging.getLogger(__name__)


class OpenAlexCollector(IPluginRESTCollector):
    related_corpus = "openalex"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))
        self.pdf_size_file_limit: int = int(os.getenv("PDF_SIZE_FILE_LIMIT", 2000000))

        team_email = os.getenv("TEAM_EMAIL")
        if not isinstance(team_email, str):
            raise ValueError("Please define TEAM_EMAIL in environment variable")
        self.team_email = team_email

    @staticmethod
    def _invert_abstract(inv_index: dict[str, list[int]]) -> str:
        if inv_index is not None:
            l_inv = [(w, p) for w, pos in inv_index.items() for p in pos]
            return " ".join(map(lambda x: x[0], sorted(l_inv, key=lambda x: x[1])))

    def _generate_api_query_params(
        self, urls: List[str], page_ln: int
    ) -> Dict[str, str | bool | int]:
        return {
            "filter": f"ids.openalex:{'|'.join(urls)}",
            "per_page": page_ln,
            "mailto": self.team_email,
            "select": "title,ids,language,abstract_inverted_index,publication_date,authorships,open_access,best_oa_location,publication_date,type,topics,keywords,referenced_works,related_works",
        }

    def _get_pdf_content(self, url: str, file_size_limit: int | None = None) -> str:
        logger.info("Getting PDF content from %s", url)
        client = get_new_https_session(retry_total=0)

        if file_size_limit and file_size_limit < 0:
            raise ValueError(f"file_size_limit must be positive : {file_size_limit}")

        if file_size_limit:
            resp_head = client.head(url, headers=HEADERS, allow_redirects=True)
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
            reader = PdfReader(pdf_file)
            sizes, size_flag = large_pages_size_flag(
                reader=reader, limit=self.pdf_size_page_limit
            )

            if size_flag:
                raise PDFPagesSizeExceedLimit(f"PDF page is too heavy {sizes}")

            pdf_content, ref_content = extract_txt_from_pdf(reader=reader)

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
    def _transform_topics(original_json: dict) -> List[dict]:
        """
        Transform the topics from the original json to the format expected by the WeLearn DB
        :param original_json: Original json from OpenAlex
        :return: List of topics in the format expected by the WeLearn DB
        """
        transformed = []
        unique_items = set()  # For check every external_id is unique

        for topic in original_json:
            domain = topic["domain"]
            field = topic["field"]
            subfield = topic["subfield"]

            # Hierachical level definition
            levels = [
                (domain, 0, "domain", []),
                (field, 1, "field", [domain["id"]]),
                (subfield, 2, "subfield", [field["id"]]),
                (
                    {"id": topic["id"], "display_name": topic["display_name"]},
                    3,
                    "topic",
                    [subfield["id"]],
                ),
            ]

            # Avoid duplicate
            for item, depth, depth_name, parent_ids in levels:
                external_id = item["id"]
                if external_id not in unique_items:
                    unique_items.add(external_id)
                    transformed.append(
                        {
                            "external_id": external_id,
                            "name": item["display_name"],
                            "depth": depth,
                            "external_depth_name": depth_name,
                            "directly_contained_in": parent_ids,
                        }
                    )

        return transformed

    def _remove_useless_first_word(
        self, string_to_clear: str, useless_words: List[str]
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

    def _convert_json_in_welearn_document(
        self, to_convert_json: dict[str, Any]
    ) -> ScrapedWeLearnDocument:
        document_title = to_convert_json["title"]
        document_url = to_convert_json["ids"]["openalex"]
        document_desc = self._remove_useless_first_word(
            string_to_clear=self._invert_abstract(
                to_convert_json["abstract_inverted_index"]
            ),
            useless_words=["background", "abstract", "introduction"],
        )
        document_content = document_desc
        if to_convert_json["best_oa_location"]["pdf_url"] is None:
            pdf_flag = False
        else:
            try:
                document_content = self._get_pdf_content(
                    to_convert_json["best_oa_location"]["pdf_url"],
                    file_size_limit=self.pdf_size_file_limit,
                )
                pdf_flag = True
            except Exception as e:
                logger.exception(
                    f"PDF retrievement error, use description as content: {e}"
                )
                pdf_flag = False
        document_lang = detect(document_content)

        document_corpus = self.related_corpus
        publication_date = int(
            datetime.strptime(
                to_convert_json["publication_date"], YEAR_FIRST_DATE_FORMAT
            ).timestamp()
        )

        authors = []
        for author_info in to_convert_json["authorships"]:
            authors.append(
                {
                    "name": author_info["author"]["display_name"],
                    "misc": ",".join(author_info["raw_affiliation_strings"]),
                }
            )

        if not to_convert_json["open_access"]["is_oa"]:
            raise ClosedAccessContent()
        else:
            logger.info(f"The content {document_url} is open access")

        best_oa_location_info = to_convert_json["best_oa_location"]

        # Open Alex format is cc-by...
        license_openalex_format: str = best_oa_location_info["license"]

        if not license_openalex_format.startswith("cc"):
            raise UnauthorizedLicense()

        logger.info(f"The content {document_url} is legally usable")

        license_good_format = f"{HTTPS_CREATIVE_COMMONS}/licenses/{license_openalex_format.replace('cc-', '')}/4.0/"

        if license_good_format.lower() not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(f"{license_good_format.lower()} is not allowed")

        logger.info(f"The content {document_url} is legally usable")

        # Predicted properties
        duration = predict_duration(text=document_content, lang=document_lang)
        readability = predict_readability(text=document_content, lang=document_lang)

        document_details = {
            "publication_date": publication_date,
            "type": to_convert_json["type"],
            "doi": to_convert_json["ids"]["doi"],
            "publisher": to_convert_json["best_oa_location"]["source"][
                "host_organization_name"
            ],
            "license_url": license_good_format,
            "issn": to_convert_json["best_oa_location"]["source"]["issn_l"],
            "content_from_pdf": pdf_flag,
            "topics": self._transform_topics(to_convert_json["topics"]),
            "tags": [x.get("display_name") for x in to_convert_json["keywords"]],
            "referenced_works": to_convert_json["referenced_works"],
            "related_works": to_convert_json["related_works"],
            "duration": duration,
            "authors": authors,
            "readability": readability,
        }

        return ScrapedWeLearnDocument(
            document_title=document_title,
            document_url=document_url,
            document_lang=document_lang,
            document_content=document_content,
            document_desc=document_desc,
            document_corpus=document_corpus,
            document_details=document_details,
        )

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        page_length = 50
        sub_batches = batched(urls, page_length)
        http_client = get_new_https_session()

        collected_docs: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []
        for sub_batch in sub_batches:
            try:
                local_params = self._generate_api_query_params(
                    urls=list(sub_batch), page_ln=page_length
                )
                ret_from_openalex = http_client.get(
                    url=OPEN_ALEX_BASE_URL, params=local_params
                )

                # Compare returned list of urls from OpenAlex and the requested ones
                oa_results = ret_from_openalex.json()["results"]
                urls_from_open_alex = [
                    result["ids"]["openalex"] for result in oa_results
                ]
                not_returned_urls = [
                    url for url in list(sub_batch) if url not in urls_from_open_alex
                ]
                logger.info(f"There is {len(not_returned_urls)} not returned urls")
                error_docs.extend(not_returned_urls)

                for result in oa_results:
                    try:
                        doc = self._convert_json_in_welearn_document(result)
                        collected_docs.append(doc)
                    except Exception as e:
                        logger.exception(
                            f"Error while trying to get contents this url : {result["ids"]["openalex"]}",
                            e,
                        )
                        error_docs.append(result["ids"]["openalex"])
            except Exception as e:
                logger.exception(
                    "Error while trying to get contents from a sub batch urls",
                    e,
                )
                error_docs.extend(list(sub_batch))
                continue

        return collected_docs, error_docs
