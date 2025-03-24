import logging
from typing import Dict, List, Type

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.exceptions import InvalidPluginType, PluginNotFoundError
from welearn_datastack.plugins.files_readers import plugins_files_list
from welearn_datastack.plugins.interface import (
    IPlugin,
    IPluginFilesCollector,
    IPluginRESTCollector,
    IPluginScrapeCollector,
)
from welearn_datastack.plugins.rest_requesters import plugins_rest_list
from welearn_datastack.plugins.scrapers import plugins_scrape_list

logger = logging.getLogger(__name__)


def select_collector(
    corpus: str,
) -> IPlugin:
    """
    Select collector class based on Corpus
    :param corpus: Corpus name
    :return: Collector class
    """
    mother_classes: List[
        Type[IPluginFilesCollector | IPluginRESTCollector | IPluginScrapeCollector]
    ] = []
    mother_classes.extend(plugins_scrape_list)
    mother_classes.extend(plugins_files_list)
    mother_classes.extend(plugins_rest_list)
    logger.info("There is %s collectors classes", len(mother_classes))

    plugins_corpus: Dict[
        str, Type[IPluginFilesCollector | IPluginRESTCollector | IPluginScrapeCollector]
    ] = {}

    for collectors_classes in mother_classes:
        plugins_corpus[collectors_classes.related_corpus] = collectors_classes

    plugins_corpus = plugins_corpus
    meta_collector = plugins_corpus.get(corpus, None)

    if meta_collector is None:
        raise PluginNotFoundError(f"Collector for {corpus} not found")

    res: IPlugin

    match meta_collector.collector_type_name:
        case PluginType.FILES:
            res_file: IPluginFilesCollector = meta_collector()  # type: ignore
            res = res_file
        case PluginType.REST:
            res_rest: IPluginRESTCollector = meta_collector()  # type: ignore
            res = res_rest
        case PluginType.SCRAPE:
            res_scrape: IPluginScrapeCollector = meta_collector()  # type: ignore
            res = res_scrape
        case _:
            raise InvalidPluginType(
                "Invalid plugin type %s", meta_collector.collector_type_name
            )
    logger.info("%s collector was selected", res.__class__.__name__)

    return res
