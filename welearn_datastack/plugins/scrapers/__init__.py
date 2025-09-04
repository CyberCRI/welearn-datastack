from typing import List, Type

from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.plugins.scrapers.conversation import ConversationCollector
from welearn_datastack.plugins.scrapers.oe_books import OpenEditionBooksCollector
from welearn_datastack.plugins.scrapers.peerj import PeerJCollector
from welearn_datastack.plugins.scrapers.plos import PlosCollector
from welearn_datastack.plugins.scrapers.unccelearn import UNCCeLearnCollector

plugins_scrape_list: List[Type[IPluginScrapeCollector]] = [
    ConversationCollector,
    PeerJCollector,
    PlosCollector,
    OpenEditionBooksCollector,
    UNCCeLearnCollector,
]
