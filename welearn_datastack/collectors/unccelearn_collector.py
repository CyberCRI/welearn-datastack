import logging
from typing import List

from bs4 import BeautifulSoup
from requests import Response
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.constants import HEADERS
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.exceptions import NotEnoughData
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class UNCCeLearnURLCollector(URLCollector):
    def __init__(self, corpus: Corpus | None) -> None:
        self.corpus = corpus
        self.base_url = "https://unccelearn.org/courses/"

    def collect(self) -> List[WeLearnDocument]:
        """
        Collect the URLs of the books and their chapters.
        :return:
        """
        # Get last books
        logger.info("Getting last book from UNCCeLearn...")
        client = get_new_https_session()
        resp: Response = client.get(url=self.base_url, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, features="html.parser")
        courses = soup.find_all("article", class_="course-card")

        if not courses:
            raise NotEnoughData("There is no data from UNCCeLearn")

        logger.info(f"Got {len(courses)} courses from UNCCeLearn")
        ret: List[WeLearnDocument] = []

        url_template = "https://unccelearn.org/course/view.php?id=<ID_TO_REPLACE>&page=overview&lang=en"

        for course in courses:
            course_id = course.get("data-courseid")
            if not course_id:
                continue
            course_url = url_template.replace("<ID_TO_REPLACE>", course_id)

            ret.append(WeLearnDocument(url=course_url, corpus=self.corpus))

        return ret
