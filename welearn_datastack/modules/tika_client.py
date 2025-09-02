import io
import os
import re

from bs4 import BeautifulSoup

from welearn_datastack.data.enumerations import TikaReturnType
from welearn_datastack.utils_.http_client_utils import get_new_https_session


class TikaClient:
    def __init__(self, default_no_ocr: bool = True) -> None:
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")
        if not self.tika_address:
            raise ValueError("TIKA_ADDRESS environment variable is not set")
        self.tika_address = self.tika_address.rstrip("/")

        if default_no_ocr:
            self.headers = {
                "X-Tika-PDFOcrStrategy": "no_ocr",
            }
        else:
            self.headers = {}

    def tika(
        self,
        file_content: io.BytesIO,
        return_type: TikaReturnType = TikaReturnType.JSON,
    ) -> dict:
        """
        Send a document to Tika micro service and return the content as a dictionary
        :param file_content: the document content as a byte stream
        :param return_type: the return type of the content (JSON, TEXT, HTML, XML)
        :raises ValueError: if the return type is not supported
        :raises requests.HTTPError: if the request to Tika micro service fails
        :return: the content returned by Tika micro service as a dictionary (JSON)
        """
        local_headers = {
            "Accept": return_type.value,
            "Content-type": "application/octet-stream",
        }

        with get_new_https_session() as http_session:
            resp = http_session.put(
                url=pdf_process_addr,
                files={"file": file_content},
                headers=local_headers,
            )
            resp.raise_for_status()
            tika_content = resp.json()
        return tika_content

    def parse_tika_content(tika_content: dict) -> list[list[str]]:
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
