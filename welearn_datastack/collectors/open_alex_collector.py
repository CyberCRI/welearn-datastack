import logging
import math
import os
from abc import ABC
from datetime import datetime
from typing import Dict, List
from zoneinfo import ZoneInfo

from welearn_datastack.constants import OPEN_ALEX_BASE_URL
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class OpenAlexURLCollector(URLCollector, ABC):
    def __init__(self, corpus: Corpus, date_last_insert: int):
        self.corpus = corpus
        self.date_last_insert = date_last_insert
        self.team_email = os.getenv("TEAM_EMAIL")

    @staticmethod
    def _get_oa_json(http_session, params):
        resp_from_openalex = http_session.get(url=OPEN_ALEX_BASE_URL, params=params)
        json_from_oa = resp_from_openalex.json()
        return json_from_oa

    def _generate_api_query_params(self) -> Dict[str, str | bool | int]:
        """
        Generate the API query to get the OpenAlex works
        :return: the API query to get the OpenAlex works
        """
        # Query params : https://docs.openalex.org/how-to-use-the-api/api-overview
        str_format_date_iso = "%Y-%m-%d"
        from_date: str = datetime.fromtimestamp(
            self.date_last_insert, tz=ZoneInfo("GMT")
        ).strftime(str_format_date_iso)
        to_date = datetime.now().strftime(str_format_date_iso)

        # Show only the content which is under creative commons or public domain
        licenses = "licenses/cc-by|licenses/cc-by-sa|licenses/public-domain"

        # Show only content not retracted by his authors
        is_retracted = "false"

        # Gold because it's better https://u-paris.fr/bibliotheques/wp-content/uploads/sites/34/2021/02/06-OPEN-ACCESS.pdf
        # But could be extended to hybrid
        oa_status = "gold"

        # Open Alex code for source we aldready have
        # In this order :
        # PLoS one, HAL, PeerJ, PeerJ Computer Science, PeerJ Physical Chemistry,
        # PLOS Global Public Health, PLOS Water, PLOS Climate, PLOS Digital Health, PLOS Sustainability and Transformation
        # PLOS Computational Biology, PLOS Biology, PLOS genetics, PLOS medicine, PLOS Mental Health,
        # PLOS Neglected Tropical Diseases, PLOS pathogens
        sources_to_avoid = "s202381698|s4306402512|s1983995261|s4210178049|s4210220408|s4210231901|s4220651631|s4220650797|s4210221150|s4220651226|s86033158|s154343897|s103870658|s197939330|s4404663781|s46544255|s2004986"
        lang = "languages/en|languages/fr"
        type_ = "types/article|types/report|types/book|types/book-chapter"

        params: Dict[str, str | bool | int] = {
            "filter": f"best_oa_location.license:{licenses},"
            f"is_retracted:{is_retracted},"
            f"open_access.oa_status:{oa_status},"
            f"primary_location.source.id:!{sources_to_avoid},"
            f"language:{lang},"
            f"from_publication_date:{from_date},"
            f"to_publication_date:{to_date},"
            f"type:{type_}",
            "sort": "publication_date:desc",
            "per_page": 200,
            "apc_sum": False,
            "cited_by_count_sum": False,
            "select": "id",
            "cursor": "*",
            "mailto": self.team_email,
        }
        return params

    def collect(self) -> List[WeLearnDocument]:
        http_session = get_new_https_session()
        params = self._generate_api_query_params()

        json_from_oa = self._get_oa_json(http_session, params)

        # Compute quantity of needed iteration
        total = int(json_from_oa["meta"]["count"])
        result_per_page = params["per_page"]

        if type(result_per_page) is not int:
            raise ValueError(f"'per_page' is not a int :{type(result_per_page)}")

        iteration_quantity = math.ceil(total / result_per_page)
        logger.info(
            f"We need {iteration_quantity} to retrieve all works with these parameters"
        )

        ret: List[WeLearnDocument] = []
        for i in range(0, iteration_quantity):
            logger.info(f"Iteration {i+1}/{iteration_quantity}")
            for work in json_from_oa["results"]:
                ret.append(WeLearnDocument(url=work["id"], corpus=self.corpus))

            if json_from_oa["meta"]["next_cursor"]:
                params["cursor"] = json_from_oa["meta"]["next_cursor"]
                json_from_oa = self._get_oa_json(http_session, params)

        return ret
