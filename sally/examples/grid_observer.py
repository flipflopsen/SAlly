import sys
from abc import ABC, abstractmethod
from typing import List, Any, Dict, Optional

from dependency_injector import containers, providers

from sally.core.config import config
from dependency_injector.wiring import inject, Provide


class Observer(ABC):
    @abstractmethod
    def update(self, subject: Any) -> None:
        pass


class Subject:
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    def notify(self) -> None:
        for observer in list(self._observers):
            observer.update(self)


class SmartGridDatabase:
    def __init__(self):
        self._data: Dict[str, Any] = {"voltage": 230.0, "frequency": 50.0, "demand": 1000.0}
        print(f"SmartGridDatabase: Initialized with test_data: {self._data}")

    def get_data(self) -> Dict[str, Any]:
        print("SmartGridDatabase: get_data() called.")
        return self._data.copy()

    def update_data(self, key: str, value: Any) -> None:
        print(f"SmartGridDatabase: update_data() called for {key}={value}.")
        self._data[key] = value


class DataCollector(Subject):
    def __init__(self, db: SmartGridDatabase):
        super().__init__()
        self._db = db
        self._current_data: Optional[Dict[str, Any]] = None
        print("DataCollector: Initialized.")

    def collect_data(self) -> None:
        print("DataCollector: collect_data() called.")
        new_data = self._db.get_data()
        if new_data != self._current_data:
            print("DataCollector: Data has changed. Notifying observers.")
            self._current_data = new_data
            self.notify()
        else:
            print("DataCollector: Data has not changed since last collection.")

    @property
    def current_data(self) -> Optional[Dict[str, Any]]:
        return self._current_data


class DataEvaluator:
    def __init__(self, data_collector: DataCollector):
        self._data_collector = data_collector
        print("DataEvaluator: Initialized.")

    def perform_analysis(self) -> str:
        print("DataEvaluator: perform_analysis() called.")
        data = self._data_collector.current_data
        if not data:
            return "No test_data available for analysis."

        if data.get("demand", 0.0) > 1200.0:
            return "High demand detected."
        if data.get("voltage", 0.0) < 220.0:
            return "Low voltage detected."
        return "System parameters are nominal."


class GridObserver(Observer):
    def __init__(self, name: str, evaluator: DataEvaluator):
        self.name = name
        self._evaluator = evaluator
        print(f"GridObserver '{self.name}': Initialized.")

    def update(self, subject: DataCollector) -> None:
        print(f"GridObserver '{self.name}': Received update from DataCollector.")
        if isinstance(subject, DataCollector):
            observed_data = subject.current_data
            print(f"GridObserver '{self.name}': Observed new test_data: {observed_data}")

            # Use the evaluator to get an analysis
            analysis_result = self._evaluator.perform_analysis()
            print(f"GridObserver '{self.name}': Evaluation result - \"{analysis_result}\"")
        else:
            print(f"GridObserver '{self.name}': Received update from an unexpected subject type.")


class AppContainer(containers.DeclarativeContainer):
    config = providers.Configuration(
        yaml_files=[str(config.get_path("config_dir") / "default.yml")],
        strict=True
    )

    database = providers.Singleton(SmartGridDatabase)

    data_collector = providers.Singleton(
        DataCollector,
        db=database
    )

    data_evaluator = providers.Singleton(  # Could be Factory if stateful and needing multiple instances
        DataEvaluator,
        data_collector=data_collector
    )

    # Using Singleton for observer here, meaning one instance of this specific observer.
    # If multiple, distinct observers of this type were needed, Factory would be suitable.
    grid_status_observer = providers.Singleton(
        GridObserver,
        name="MainGridStatusObserver",  # Name injected into observer
        evaluator=data_evaluator
    )

@inject
def run_simulation(
        collector: DataCollector = Provide[AppContainer.data_collector],
        observer: GridObserver = Provide[AppContainer.grid_status_observer],
        db: SmartGridDatabase = Provide[AppContainer.database]  # Inject db to simulate external changes
) -> None:
    print("\n--- Smart Grid Simulation Start ---")

    # Register the observer with the test_data collector (subject)
    collector.attach(observer)

    # Initial test_data collection
    print("\n[Step 1: Initial test_data collection]")
    collector.collect_data()

    # Simulate a change in the database (e.g., demand increases)
    print("\n[Step 2: Simulating database change - demand increase]")
    db.update_data("demand", 1500.0)
    collector.collect_data()  # This should trigger notification and observer update

    # Simulate another change (e.g., voltage drops)
    print("\n[Step 3: Simulating database change - voltage drop]")
    db.update_data("voltage", 210.0)
    db.update_data("demand", 1100.0)  # Reset demand
    collector.collect_data()

    # Simulate a scenario where test_data doesn't change
    print("\n[Step 4: Simulating no test_data change]")
    collector.collect_data()  # Should not trigger notification if test_data is same

    # Detach observer and simulate another change
    print("\n[Step 5: Detaching observer and simulating database change - frequency change]")
    collector.detach(observer)
    db.update_data("frequency", 50.5)
    collector.collect_data()  # Observer should not receive this update

    print("\n--- Smart Grid Simulation End ---")


if __name__ == "__main__":
    container = AppContainer()
    container.wire(modules=[sys.modules[__name__]])

    run_simulation()
