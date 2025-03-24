from typing import List, Type

from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.plugins.rest_requesters.hal import HALCollector
from welearn_datastack.plugins.rest_requesters.oapen import OAPenCollector
from welearn_datastack.plugins.rest_requesters.open_alex import OpenAlexCollector
from welearn_datastack.plugins.rest_requesters.ted import TEDCollector
from welearn_datastack.plugins.rest_requesters.wikipedia import WikipediaCollector

plugins_rest_list: List[Type[IPluginRESTCollector]] = [
    WikipediaCollector,
    HALCollector,
    TEDCollector,
    OAPenCollector,
    OpenAlexCollector,
]
