from abc import ABC, abstractmethod
from typing import List, Any, Dict, Optional
from sally.infrastructure.data_management.base_data_manager import BaseCollector, BaseAdapter
from sally.core.observer import Subject


class SmartGridDatabase(BaseAdapter):
    """
    Simulated database for smart grid state test_data.
    """

    def __init__(self):
        self._data: Dict[str, Any] = {"voltage": 230.0, "frequency": 50.0, "demand": 1000.0}
        print(f"SmartGridDatabase: Initialized with test_data: {self._data}")

    def get_data(self) -> Dict[str, Any]:
        """
        Retrieves the current state test_data from the database.
        """
        print("SmartGridDatabase: get_data() called.")
        # In a real scenario, this would query a database like PostgreSQL.
        return self._data.copy()

    def update_data(self, key: str, value: Any) -> None:
        """
        Updates a specific piece of test_data in the database.
        """
        print(f"SmartGridDatabase: update_data() called for {key}={value}.")
        self._data[key] = value
        # In a real PostgreSQL setup, this might be where a LISTEN/NOTIFY trigger occurs
        # or where test_data changes for the next polling cycle.


class SGDataCollector(BaseCollector, Subject):
    """
    Collects test_data from the database and acts as a Subject.
    Notifies observers when test_data changes.
    """

    def __init__(self, db: SmartGridDatabase):
        super().__init__()
        self._db = db
        self._current_data: Optional[Dict[str, Any]] = None
        print("DataCollector: Initialized.")

    def collect_data(self) -> None:
        """
        Fetches test_data from the database and notifies observers if it has changed.
        """
        print("DataCollector: collect_data() called.")
        new_data = self._db.get_data()
        if new_data != self._current_data:
            print("DataCollector: Data has changed. Notifying observers.")
            self._current_data = new_data
            self.notify()  # Notify observers about the change
        else:
            print("DataCollector: Data has not changed since last collection.")

    @property
    def current_data(self) -> Optional[Dict[str, Any]]:
        return self._current_data
