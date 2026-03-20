"""
Tests for sally.core.observer — Observer / Subject pattern.

Covers: Observer ABC, Subject (attach, detach, notify).
"""

from __future__ import annotations

import pytest

from sally.core.observer import Observer, Subject
from tests.diag.metrics import record_metric


class _ConcreteObserver(Observer):
    """Simple concrete observer for testing."""

    def __init__(self):
        self.updates: list = []

    def update(self, subject):
        self.updates.append(subject)


class _ConcreteSubject(Subject):
    """Simple concrete subject for testing."""

    def __init__(self):
        super().__init__()
        self.state = 0

    def set_state(self, state):
        self.state = state
        self.notify()


class TestObserver:
    def test_abstract_class(self):
        with pytest.raises(TypeError):
            Observer()  # type: ignore
        record_metric("observer_abstract", 1, "bool")


class TestSubject:
    def test_attach_and_notify(self):
        s = _ConcreteSubject()
        o = _ConcreteObserver()
        s.attach(o)
        s.set_state(42)
        assert len(o.updates) == 1
        assert o.updates[0].state == 42
        record_metric("subject_attach_notify", 1, "bool")

    def test_multiple_observers(self):
        s = _ConcreteSubject()
        o1 = _ConcreteObserver()
        o2 = _ConcreteObserver()
        s.attach(o1)
        s.attach(o2)
        s.set_state(10)
        assert len(o1.updates) == 1
        assert len(o2.updates) == 1
        record_metric("subject_multi_observer", 2, "observers")

    def test_detach(self):
        s = _ConcreteSubject()
        o = _ConcreteObserver()
        s.attach(o)
        s.detach(o)
        s.set_state(99)
        assert len(o.updates) == 0
        record_metric("subject_detach", 1, "bool")

    def test_detach_nonexistent_observer(self):
        s = _ConcreteSubject()
        o = _ConcreteObserver()
        # Should not raise
        s.detach(o)
        record_metric("subject_detach_nonexist", 1, "bool")

    def test_no_duplicate_attach(self):
        s = _ConcreteSubject()
        o = _ConcreteObserver()
        s.attach(o)
        s.attach(o)  # duplicate
        s.set_state(5)
        assert len(o.updates) == 1  # only notified once
        record_metric("subject_no_dup_attach", 1, "bool")

    def test_notify_order(self):
        s = _ConcreteSubject()
        order = []
        for i in range(5):
            obs = _ConcreteObserver()
            obs.id = i
            obs.update = lambda subj, _id=i: order.append(_id)
            s.attach(obs)
        s.notify()
        assert order == [0, 1, 2, 3, 4]
        record_metric("subject_notify_order", len(order), "items")

    def test_observer_detach_during_notify(self):
        """Observers can safely detach during iteration (iterates copy)."""
        s = _ConcreteSubject()
        detacher = _ConcreteObserver()

        def detach_self(subj):
            s.detach(detacher)
            detacher.updates.append(subj)

        detacher.update = detach_self
        s.attach(detacher)
        s.set_state(1)  # should not raise
        assert len(detacher.updates) == 1
        # Second notification - detacher is gone
        s.set_state(2)
        assert len(detacher.updates) == 1
        record_metric("subject_detach_during_notify", 1, "bool")
