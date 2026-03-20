"""
Tests for sally.infrastructure.data_management

Covers: BaseCollector ABC, BaseAdapter ABC,
        SmartGridDatabase, SGDataCollector.
"""

from __future__ import annotations

from tests.diag.metrics import record_metric


class TestBaseCollectorABC:
    def test_cannot_instantiate(self):
        from sally.infrastructure.data_management.base_data_manager import BaseCollector

        raised = False
        try:
            BaseCollector()
        except TypeError:
            raised = True
        assert raised
        record_metric("base_collector_abc", 1, "bool")


class TestBaseAdapterABC:
    def test_cannot_instantiate(self):
        from sally.infrastructure.data_management.base_data_manager import BaseAdapter

        raised = False
        try:
            BaseAdapter()
        except TypeError:
            raised = True
        assert raised
        record_metric("base_adapter_abc", 1, "bool")


class TestSmartGridDatabase:
    def test_initial_data(self):
        from sally.infrastructure.data_management.sg.smartgrid_db_adapter import SmartGridDatabase

        db = SmartGridDatabase()
        data = db.get_data()
        assert "voltage" in data
        assert "frequency" in data
        assert "demand" in data
        assert data["voltage"] == 230.0
        record_metric("sg_db_init", len(data), "fields")

    def test_update_data(self):
        from sally.infrastructure.data_management.sg.smartgrid_db_adapter import SmartGridDatabase

        db = SmartGridDatabase()
        db.update_data("voltage", 240.0)
        assert db.get_data()["voltage"] == 240.0
        record_metric("sg_db_update", 1, "bool")

    def test_get_data_returns_copy(self):
        from sally.infrastructure.data_management.sg.smartgrid_db_adapter import SmartGridDatabase

        db = SmartGridDatabase()
        data1 = db.get_data()
        data1["voltage"] = 999
        assert db.get_data()["voltage"] == 230.0  # unchanged
        record_metric("sg_db_copy", 1, "bool")


class TestSGDataCollector:
    def test_collect_data_notifies_observers(self):
        from sally.infrastructure.data_management.sg.smartgrid_db_adapter import (
            SmartGridDatabase, SGDataCollector,
        )
        from sally.core.observer import Observer

        notified = []

        class Spy(Observer):
            def update(self, subject):
                notified.append(True)

        db = SmartGridDatabase()
        collector = SGDataCollector(db)
        spy = Spy()
        collector.attach(spy)

        collector.collect_data()
        assert len(notified) == 1
        assert collector.current_data is not None
        record_metric("sg_collector_notify", len(notified), "notifications")

    def test_collect_data_no_change_no_notify(self):
        from sally.infrastructure.data_management.sg.smartgrid_db_adapter import (
            SmartGridDatabase, SGDataCollector,
        )
        from sally.core.observer import Observer

        notified = []

        class Spy(Observer):
            def update(self, subject):
                notified.append(True)

        db = SmartGridDatabase()
        collector = SGDataCollector(db)
        spy = Spy()
        collector.attach(spy)

        collector.collect_data()  # First → notifies
        collector.collect_data()  # Same data → no notify
        assert len(notified) == 1
        record_metric("sg_collector_nochange", 1, "bool")

    def test_collect_data_detects_change(self):
        from sally.infrastructure.data_management.sg.smartgrid_db_adapter import (
            SmartGridDatabase, SGDataCollector,
        )
        from sally.core.observer import Observer

        notified = []

        class Spy(Observer):
            def update(self, subject):
                notified.append(True)

        db = SmartGridDatabase()
        collector = SGDataCollector(db)
        spy = Spy()
        collector.attach(spy)

        collector.collect_data()  # First → notifies
        db.update_data("voltage", 240.0)
        collector.collect_data()  # Changed → notifies again
        assert len(notified) == 2
        record_metric("sg_collector_change", 2, "notifications")
