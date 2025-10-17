from abc import ABC, abstractmethod
from typing import List

from welearn_database.data.models import WeLearnDocument


class URLCollector(ABC):
    @abstractmethod
    def collect(self) -> List[WeLearnDocument]:
        """
        Collect urls from various sources
        :return: List of URLDataStore
        """
        pass
