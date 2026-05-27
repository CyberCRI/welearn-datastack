import io
from typing import Any

from bs4 import BeautifulSoup
from refinedoc.refined_document import RefinedDocument

from welearn_datastack.utils_.http_client_utils import get_new_https_session


class TikaPDFDocument:
    def __init__(self, raw_pdf_content: io.BytesIO, tika_base_url: str):
        self._raw_pdf_content = raw_pdf_content
        self._tika_base_url = tika_base_url
        self.tika_content = self._send_pdf_to_tika(self._raw_pdf_content, self._tika_base_url)
        self._pdf_content = self._parse_tika_content(self.tika_content)
        self._refined_pdf_content = RefinedDocument(content=self._pdf_content)

    @staticmethod
    def _send_pdf_to_tika(pdf_content: io.BytesIO, tika_base_url: str) -> dict:
        """
        Send a PDF document to Tika micro service and return the content as a dictionary
        :param pdf_content: the PDF document content as a byte stream
        :param tika_base_url: the base URL of the Tika micro service
        :return: the content returned by Tika micro service as a dictionary (JSON)
        """
        if tika_base_url.endswith("/"):
            tika_base_url = tika_base_url[:-1]
        pdf_process_addr = f"{tika_base_url}/tika"
        local_headers = {
            "Accept": "application/json",
            "Content-type": "application/octet-stream",
            "X-Tika-PDFOcrStrategy": "no_ocr",
        }

        with get_new_https_session() as http_session:
            resp = http_session.put(
                url=pdf_process_addr,
                files={"file": pdf_content},
                headers=local_headers,
            )
            resp.raise_for_status()
            tika_content = resp.json()
        return tika_content

    @staticmethod
    def _parse_tika_content(tika_content: dict) -> list[list[str]]:
        """
        Parse the content returned by Tika micro service
        :param tika_content: the content returned by Tika micro service
        :return: the parsed content as a list of list of strings (one list per page
        """
        htmlx = tika_content.get("X-TIKA:content")
        soup = BeautifulSoup(htmlx, features="html.parser")
        pages = soup.find_all("div", {"class": "page"})
        res = [p.split("\n") for p in [page.get_text() for page in pages]]

        return res

    @property
    def body(self) -> list[list[Any]] | None:
        return self._refined_pdf_content.body

    @property
    def headers(self) -> list[list[Any]] | None:
        return self._refined_pdf_content.headers

    @property
    def footers(self) -> list[list[Any]] | None:
        return self._refined_pdf_content.footers

    @staticmethod
    def _compute_parse_precision(
        chars_per_page: list[int], total_unmapped_unicode_chars: int
    ) -> float:
        """
        Compute the parse precision of the Tika micro service for a PDF document
        :param chars_per_page: the number of characters per page of the PDF document
        :param total_unmapped_unicode_chars: the total number of unmapped unicode characters in the PDF document
        :return: the parse precision as a float between 0 and 1
        """
        total_chars = sum(chars_per_page)
        if total_chars == 0:
            return 0.0
        return (total_chars - total_unmapped_unicode_chars) / total_chars

    def _compute_parse_precision_from_tika_content(self, tika_content: dict) -> float:
        """
        Compute the parse precision of the Tika micro service for a PDF document from the content returned by Tika micro service
        :param tika_content: the content returned by Tika micro service
        :return: the parse precision as a float between 0 and 1
        """
        chars_per_page = tika_content.get("pdf:charsPerPage", [])
        total_unmapped_unicode_chars = tika_content.get("pdf:totalUnmappedUnicodeChars", 0)
        return self._compute_parse_precision(chars_per_page, total_unmapped_unicode_chars)

    @property
    def precision(self)-> float:
        return self._compute_parse_precision_from_tika_content(self.tika_content)
