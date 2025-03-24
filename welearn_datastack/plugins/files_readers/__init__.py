from typing import List, Type

from welearn_datastack.plugins.files_readers.conversation import (
    CSVConversationCollector,
)
from welearn_datastack.plugins.files_readers.france_culture import (
    CSVFranceCultureCollector,
)
from welearn_datastack.plugins.files_readers.hal import JsonHALCollector
from welearn_datastack.plugins.files_readers.plos import XMLPLOSCollector
from welearn_datastack.plugins.files_readers.ted import CSVTedCollector
from welearn_datastack.plugins.files_readers.wikipedia import CSVWikipediaCollector
from welearn_datastack.plugins.interface import IPluginFilesCollector

plugins_files_list: List[Type[IPluginFilesCollector]] = [
    CSVConversationCollector,
    CSVWikipediaCollector,
    CSVTedCollector,
    CSVFranceCultureCollector,
    JsonHALCollector,
    XMLPLOSCollector,
]
