from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseCollector(ABC):
    @abstractmethod
    def collect_data(self) -> None:
        pass

    @abstractmethod
    def current_data(self) -> Optional[Dict[str, Any]]:
        pass


class BaseAdapter(ABC):
    @abstractmethod
    def get_data(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_data(self, key: str, value: Any) -> None:
        pass