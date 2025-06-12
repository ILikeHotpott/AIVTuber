from abc import ABC, abstractmethod
from typing import List, Dict


class MemoryRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, k: int = 3) -> List[Dict]:
        ...
