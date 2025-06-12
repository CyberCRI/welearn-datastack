import logging
import math
import os
from abc import ABC
from datetime import datetime
from typing import Dict, List
from zoneinfo import ZoneInfo

from welearn_datastack.constants import OPEN_ALEX_BASE_URL, PUBLISHERS_TO_AVOID
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
        logger.info(f"OpenAlex response status code: {resp_from_openalex.status_code}")
        resp_from_openalex.raise_for_status()
        json_from_oa = resp_from_openalex.json()
        return json_from_oa

    def _generate_api_query_params(self) -> Dict[str, str | bool | int | None]:
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

        # Open Alex code for the 100 first (open alex API limitation) publishers we don't want to retrieve (According to https://www.predatoryjournals.org/the-list/publishers)
        # In this order :
        # Canadian Center of Science and Education, Academic Journals, Lectito Journals, Pulsus Group, Business Perspectives,
        # Econjournals, Frontiers, Multidisciplinary Digital Publishing Institute (MDPI), WIT Press, Qingres, NobleResearch,
        # TSNS “Interaktiv plus”, LLC, Science and Education Centre of North America, Medical science, AEPress,
        # Scientific Journals, Atlas Publishing, LP, Baishideng Publishing Group, National Association of Scholars,
        # Allied Academies, Smart Science & Technology, Lupine Publishers, Ivy Union Publishing, PiscoMed Publishing,
        # Scientia Socialis, Scientia Socialis, SciPress Ltd, Australian International Academic Centre Pty. Ltd., Eurasian Publications,
        # Access Journals, Open Access Journals, Open Access Library, Applied Science Innovations, AgiAl Publishing House,
        # Tomas Publishing, Herbert Open Access Journals (Herbert Publications), Publishing Press, World Scientific Publishing,
        # Hindawi, Research Publishing Group, Science and Technology Publishing, Lectito, MedCrave, American Journal,
        # New Century Science Press, New Science, International Scientific Publications,
        # ISPACS (International Scientific Publications and Consulting Services),
        # International Foundation for Research and Development, IGI Global, Scientific Research Publishing (SCIRP),
        # Sciedu Press, e-Century Publishing Corporation, American Scientific Publishers, SciTechnol, Virtus Interpress,
        # Oriental Scientific Publishing Company, Center for Promoting Ideas, Excellent Publishers, IGM Publication, OPAST,
        # Medip Academy, Medip Academy, Academic Sciences, Innovare Academic Sciences, Medtext Publications, Globeedu Group,
        # Research Journal, Galore Knowledge Publication Pvt. Ltd., Scientific Education, Gupta Publications,
        # International Information Institute, Innovative Journals, Asian Research Consortium,
        # The International Association for Information, Culture, Human and Industry Technology,
        # Sci Forschen, Horizon Research Publishing, Lawarence Press, AI Publications, Kowsar Publishing, Hilaris, Sadguru Publications,
        # Institute of Advanced Scientific Research, International Educative Research Foundation And Publisher, Research Publisher,
        # Open Access Publishing Group, Advanced Research Publications, Open Science, Society of Education, Elmer Press,
        # Macrothink Institute, Universe Scientific Publishing, IJRCM, Auctores Publishing, LLC, Management Journals,
        # Scholars Research Library, Academy Journals, International Journals of Multidisciplinary Research Academy,
        # Multidisciplinary Journals, Science Publishing Group
        #
        # Not filtered by OpenAlex API but we don't want to retrieve them :
        # WFL Publisher, Open Journal Systems, EnPress Publisher, CARI Journals, Pushpa Publishing House,
        # Global Vision Press, RedFame Publishing, i-manager Publications, Infogain Publication,
        # International Digital Organization for Scientific Information (IDOSI), Blue Eyes Intelligence Engineering & Sciences Publication,
        # Academia Research, Academic Research Publishing Group, Hikari Ltd., Enviro Publishers / Enviro Research Publishers,
        # GRDS Publishing, Internet Scientific Publications, JSciMed Central, International Academy of Business, Remedy Publications, TMR Publishing Group
        publishers_to_avoid = "|".join(PUBLISHERS_TO_AVOID[:100])
        lang = "languages/en|languages/fr"
        type_ = "types/article|types/report|types/book|types/book-chapter"

        params: Dict[str, str | bool | int | None] = {
            "filter": f"best_oa_location.license:{licenses},"
            f"is_retracted:{is_retracted},"
            f"open_access.oa_status:{oa_status},"
            f"primary_location.source.id:!{sources_to_avoid},"
            f"primary_location.source.publisher_lineage:!{publishers_to_avoid},"
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
