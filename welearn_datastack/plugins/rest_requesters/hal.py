import io
import logging
import os
from datetime import datetime, timezone
from itertools import batched
from typing import Any, Iterable, List, Tuple

from pypdf import PdfReader
from urllib3 import Retry

from welearn_datastack.constants import AUTHORIZED_LICENSES, HAL_URL_BASE
from welearn_datastack.data.enumerations import DeletePart
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import NoContent, PDFPagesSizeExceedLimit
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    delete_pages,
    delete_redundant_content,
    extract_txt_from_pdf,
    large_pages_size_flag,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import get_url_without_hal_like_versionning

logger = logging.getLogger(__name__)


explicit_types = {
    "ART": "article",
    "COMM": "communication",
    "COUV": "chapter",
    "THESE": "thesis",
    "OUV": "book",
    "MEM": "dissertation",
    "REPORT": "report",
    "UNDEFINED": "preprint",
}

AUTHORIZED_LICENSES_WITHOUT_VERSION = []

for license_ in AUTHORIZED_LICENSES:
    splt_license = license_.split("/")[:-2]
    AUTHORIZED_LICENSES_WITHOUT_VERSION.append("/".join(splt_license) + "/")


LOCAL_LICENSES = [
    "http://hal.archives-ouvertes.fr/licences/publicDomain/",
]


HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "TE": "Trailers",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
}

RETRY_STRATEGY = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
)


class HALCollector(IPluginRESTCollector):
    related_corpus = "hal"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True

        # Query params : https://api.archives-ouvertes.fr/docs/search/?schema=fields#fields
        self._query_params_doctype_s = (
            "ART+OR+COMM+OR+OUV+OR+COUV+OR+DOUV+OR+OTHER+OR+THESE+OR+HDR+OR+LECTURE"
        )
        self._query_params_fl = "docid,authFullName_s,docType_s,title_s,language_s,publicationDate_tdate,producedDate_tdate,uri_s,fulltext_t,abstract_s,licence_s,fileMain_s,halId_s"
        self._query_params_wt = "json"
        self._query_params_sort = "docid asc"
        self._quantity_rows_retruned = "10000"  # 30 by default, 10000 max
        self.licenses = AUTHORIZED_LICENSES_WITHOUT_VERSION + LOCAL_LICENSES
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))

    @staticmethod
    def _convert_hal_date_to_ts(hal_dt: str) -> float | None:
        """
        Convert a HAL date to a timestamp
        :param hal_dt: HAL date
        :return: Timestamp
        """
        only_date = hal_dt.split("T")[0]
        time_format = "%Y-%m-%d"

        if not hal_dt:
            return None
        dt = datetime.strptime(only_date, time_format)
        dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    @staticmethod
    def _create_halids_query(hal_ids: List[str]) -> str:
        """
        Return a str formated for the HAL API
        eg : halId_s:(hal-00006805 OR hal-00333300)
        :param hal_ids: List of HAL IDs
        :return: str
        """
        if len(hal_ids) == 1:
            return "halId_s:" + hal_ids[0]
        return "halId_s:(" + " OR ".join(hal_ids) + ")"

    @staticmethod
    def _extract_hal_ids(urls: Iterable[str]) -> List[str]:
        """
        Extract HAL IDs from a list of urls
        :param urls: List of urls
        :return: List of HAL IDs
        """
        hal_ids: List[str] = []
        for url in urls:
            hal_ids.append(url.split("/")[-1])
        return hal_ids

    @staticmethod
    def _get_hal_url(json_dict: dict) -> str:
        """
        Get the HAL URL from a JSON dict
        :param json_dict: JSON dict
        :return: HAL URL
        """
        return HAL_URL_BASE + json_dict["halId_s"]

    def _get_details_from_dict(self, json_dict: dict) -> dict[str, Any]:
        """
        Get details from a JSON dict
        :param json_dict: JSON dict
        :return: Details
        """
        raw_pub_date = json_dict.get("publicationDate_tdate", "")
        raw_prod_date = json_dict.get("producedDate_tdate", "")
        pubdate_timestamp: float | None = None
        prod_date_timestamp: float | None = None
        if raw_pub_date:
            pubdate_timestamp = self._convert_hal_date_to_ts(raw_pub_date)

        if raw_prod_date:
            prod_date_timestamp = self._convert_hal_date_to_ts(raw_prod_date)

        raw_authors: List[str] = json_dict.get("authFullName_s", [])

        details: dict[str, Any] = {
            "docid": json_dict.get("docid", ""),
            "produced_date": prod_date_timestamp,
            "type": explicit_types.get(json_dict.get("docType_s", ""), "UNDEFINED"),
            "publication_date": pubdate_timestamp,
            "authors": [{"name": author, "misc": ""} for author in raw_authors],
        }
        return details

    def _convert_json_dict_to_welearndoc(
        self, json_dict: dict
    ) -> ScrapedWeLearnDocument:
        """
        Convert a json dict to ScrapedWeLearnDocument
        :param json_dict: JSON dict
        :return: ScrapedWeLearnDocument
        """
        pdf_mode: bool = False
        doc_license: str | None = json_dict.get("licence_s", None)
        file_addr: str | None = json_dict.get("fileMain_s", None)

        logger.info("License: %s", doc_license)
        if doc_license in self.licenses and file_addr:
            logger.info("This document is an available PDF")
            pdf_mode = True

        try:
            url = self._get_hal_url(json_dict)
        except KeyError:
            raise KeyError("This line : '%s' cannot be scraped, no url", str(json_dict))

        lang_list: List[str] | None = json_dict.get("language_s", None)
        if not lang_list or len(lang_list) == 0:
            raise KeyError(
                "This line : '%s' cannot be scraped, no lang", str(json_dict)
            )
        lang: str = lang_list[0]

        if lang == "und":
            raise KeyError(
                "This line : '%s' cannot be scraped, lang undefined",
                url,
            )

        titles: List[str] | None = json_dict.get("title_s", None)
        if not titles or len(titles) == 0:
            raise KeyError("This line : '%s' cannot be scraped, no titles", url)
        title: str = titles[0]

        abstracts: List[str] | None = json_dict.get("abstract_s", None)
        if not abstracts or len(abstracts) == 0:
            raise KeyError(
                "This line : '%s' cannot be scraped, no content",
                url,
            )
        abstract: str = "".join(abstracts)
        if abstract == "absent":
            raise NoContent(
                "This line : '%s' cannot be scraped, content is absent",
                url,
            )

        if not pdf_mode:
            desc = abstract.split(".")[0]
            content = abstract
        else:
            content = self._get_pdf_content(file_addr)  # type: ignore
            desc = abstract

        details = self._get_details_from_dict(json_dict)
        details["content_from_pdf"] = pdf_mode

        current = ScrapedWeLearnDocument(
            document_title=title,
            document_url=url,
            document_lang=lang,
            document_content=content,
            document_desc=desc.strip() + "...",
            document_corpus="hal",
            document_details=details,
        )

        logger.info("Document %s successfully scraped", url)

        return current

    def _get_url_without_hal_versionning(self, json_dict: dict) -> str:
        """
        Get the URL without the versionning part
        https://hal.science/hal-04337383v1 -> https://hal.science/hal-04337383
        :param json_dict: JSON dict from HAL API
        :return: URL without versionning
        """
        uri_s: str | None = json_dict.get("uri_s", None)
        if not uri_s:
            raise KeyError("This line : '%s' cannot be scraped, no url", str(json_dict))

        return get_url_without_hal_like_versionning(uri_s)

    def _get_pdf_content(self, url: str) -> str:
        logger.info("Getting PDF content from %s", url)
        client = get_new_https_session()
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()

        pdf_file = io.BytesIO(response.content)

        reader = PdfReader(pdf_file)

        sizes, size_flag = large_pages_size_flag(
            reader=reader, limit=self.pdf_size_page_limit
        )

        if size_flag:
            raise PDFPagesSizeExceedLimit(
                f"Limit is {self.pdf_size_page_limit} and pages are {sizes}"
            )

        pdf_content, ref_content = extract_txt_from_pdf(reader=reader)

        # Delete non printable characters
        pdf_content = [
            [delete_non_printable_character(word) for word in page]
            for page in pdf_content
        ]

        # Delete before the introduction
        delete_pages(pdf_content, DeletePart.before, "introduction", ref_content)

        # Delete after the references
        synonym = ["references", "bibliography", "bibliographie", "références"]
        for word in synonym:
            delete_pages(pdf_content, DeletePart.after, word, ref_content)

        # Delete redondant content
        delete_redundant_content(pdf_content)

        pages = []
        for content in pdf_content:
            page_text = " ".join(content)
            page_text = replace_ligatures(page_text)
            page_text = remove_hyphens(page_text)
            page_text = delete_accents(page_text)

            pages.append(page_text)

        return " ".join(pages)

    def _get_jsons(self, hal_ids: List[str]) -> List[dict]:
        http = get_new_https_session()
        url = "https://api.archives-ouvertes.fr/search/"

        response = http.get(
            url,
            params={
                "q": self._create_halids_query(hal_ids),
                "doctype_s": self._query_params_doctype_s,
                "fl": self._query_params_fl,
                "wt": self._query_params_wt,
                "sort": self._query_params_sort,
                "rows": self._quantity_rows_retruned,
            },
            headers=HEADERS,
        )

        logger.info("Request URL: %s", response.request.url)
        json_req = response.json()
        docs: List = json_req["response"]["docs"]
        return docs

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        logger.info("Running HALCollectorRest plugin")
        ret: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []
        content_from_hal: List[dict] = []

        for local_url_batch in batched(urls, 100):
            try:
                hal_ids = self._extract_hal_ids(local_url_batch)
                content_from_hal.extend(self._get_jsons(hal_ids))
            except Exception as e:
                logger.error("Error while getting JSON from HAL API")
                logger.error(e)
                for url in local_url_batch:
                    error_docs.append(url)

        for doc in content_from_hal:
            try:
                ret.append(self._convert_json_dict_to_welearndoc(doc))
            except Exception as e:
                logger.exception(
                    "Error while trying to get contents for url,\n url: '%s' \nError: %s",
                    self._get_hal_url(doc),
                    e,
                )
                error_docs.append(self._get_hal_url(doc))
                continue
        logger.info(
            "HALCollectorRest plugin finished, %s urls successfully processed",
            len(ret),
        )
        return ret, error_docs
