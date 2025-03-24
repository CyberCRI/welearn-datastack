import logging
from typing import Dict, List, Tuple

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginFilesCollector
from welearn_datastack.plugins.scrapers.plos import PlosCollector

logger = logging.getLogger(__name__)


class XMLPLOSCollector(IPluginFilesCollector):
    """
    This class is a plugin to read XML from PLOS corpus
    """

    related_corpus = "xml_plos"

    def __init__(self):
        super().__init__()

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        """
        Run the plugin
        :param urls: List of urls to filter
        :return: List of ScrapedWeLearnDocument
        """
        res: List[ScrapedWeLearnDocument] = []
        error_urls: List[str] = []

        collector = PlosCollector()

        # Iterate over files
        for i, url in enumerate(urls):
            # Get file name
            logger.info("Processing url %s/%s", i, len(urls))
            article_id = url.split("/")[-1]
            file_name = f"{article_id}.xml"
            article_file_path = (
                self._resource_folder_root / type(self).__name__ / file_name
            )

            try:
                # Parse XML
                with open(article_file_path, "r") as file:
                    article = collector.extract_data_from_plos_xml(
                        txt=file.read(), url=url
                    )
                    res.append(article)
            except Exception as e:
                logger.exception(
                    "Error while scraping url,\n url: '%s' \nError: %s", url, e
                )
                error_urls.append(url)
                continue
        return res, error_urls
