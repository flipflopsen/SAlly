from abc import ABC, abstractmethod
from typing import List, Any, Dict, Optional


class Observer(ABC):
    """
    Abstract base class for all observers.
    """

    @abstractmethod
    def update(self, subject: Any) -> None:
        """
        Receive update from subject.
        """
        pass


class Subject:
    """
    Subject class that observers can subscribe to.
    It can be inherited by concrete subjects.
    """

    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer: Observer) -> None:
        """
        Attach an observer to the subject.
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """
        Detach an observer from the subject.
        """
        try:
            self._observers.remove(observer)
        except ValueError:
            pass  # Observer not found, do nothing

    def notify(self) -> None:
        """
        Notify all attached observers about an event.
        Iterates over a copy of the list in case observers detach themselves during update.
        """
        for observer in list(self._observers):
            observer.update(self)
