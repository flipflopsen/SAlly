"""Tests for the MIDAS → SAlly integration pipeline."""

import textwrap
from pathlib import Path

import pytest

from tests.diag.metrics import record_metric


pytestmark = pytest.mark.midas

from sally.infrastructure.midas.midas_parser import MidasScenarioParser
from sally.infrastructure.midas.midas_mapper import MidasToSallyMapper
from sally.application.simulation.midas import MidasSimulationAdapter


# ── Fixtures ─────────────────────────────────────────────────────────────────


# Real MIDAS YAML format: top-level scenario keys with modules + *_params
SAMPLE_SCENARIO = textwrap.dedent("""\
    test_scenario:
      modules: [store, powergrid, sndata]
      start_date: 2024-01-15 00:00:00+0100
      end: 1*24*60*60
      step_size: 15*60
      silent: true
      store_params:
        filename: test_output.csv
      powergrid_params:
        test_grid:
          gridfile: simple_four_bus_system
      sndata_params:
        test_grid:
          interpolate: true
          randomize_data: true
          active_mapping:
            2: [[Land_0, 0.75]]
            3: [[Land_3, 0.425]]

    test_scenario_der:
      parent: test_scenario
      modules: [weather, der]
      store_params:
        filename: test_output_der.csv
      weather_params:
        bremen:
          weather_mapping:
            WeatherCurrent:
              - interpolate: true
                randomize: true
      der_params:
        test_grid:
          grid_name: test_grid
          mapping:
            2: [[PV, 0.00725]]
            3: [[PV, 0.00103]]
          weather_provider_mapping:
            PV: [bremen, 0]
""")


@pytest.fixture
def scenario_file(tmp_path: Path) -> Path:
    """Write a sample YAML scenario to a temp file."""
    p = tmp_path / "test_scenario.yml"
    p.write_text(SAMPLE_SCENARIO, encoding="utf-8")
    return p


# ── Parser Tests ─────────────────────────────────────────────────────────────


class TestMidasScenarioParser:
    def test_parse_string(self):
        parser = MidasScenarioParser()
        scenario = parser.parse_string(SAMPLE_SCENARIO, name="test")

    record_metric("midas_duration_s", float(scenario.duration or 0), "s")
    record_metric("midas_step_size_s", float(scenario.step_size or 0), "s")
    record_metric("midas_modules", float(len(scenario.modules or [])), "count")
    record_metric("midas_simulators", float(len(scenario.simulators or {})), "count")
    record_metric("midas_entities", float(len(scenario.entities or [])), "count")

    assert scenario.name == "test_scenario"
    assert scenario.duration == 86400
    assert scenario.step_size == 900
    assert scenario.modules == ["store", "powergrid", "sndata"]

    def test_parse_all(self, scenario_file: Path):
        parser = MidasScenarioParser()
        scenarios = parser.parse_all(scenario_file)

        record_metric("midas_scenarios", float(len(scenarios or [])), "count")

        assert len(scenarios) == 2
        names = {s.name for s in scenarios}
        assert "test_scenario" in names
        assert "test_scenario_der" in names

    def test_parse_file(self, scenario_file: Path):
        parser = MidasScenarioParser()
        scenario = parser.parse_file(scenario_file)

        assert scenario.name == "test_scenario"
        assert scenario.source_path == scenario_file

    def test_simulators_from_modules(self):
        parser = MidasScenarioParser()
        scenario = parser.parse_string(SAMPLE_SCENARIO, name="test")

        # Each module+scope combination becomes a simulator
        assert len(scenario.simulators) > 0
        # powergrid_test_grid, sndata_test_grid, store should exist
        sim_keys = list(scenario.simulators.keys())
        assert any("powergrid" in k for k in sim_keys)
        assert any("sndata" in k for k in sim_keys)

    def test_entities_inferred_from_params(self):
        parser = MidasScenarioParser()
        scenario = parser.parse_string(SAMPLE_SCENARIO, name="test")

        # Should infer grid entity and load entities from sndata_params
        assert len(scenario.entities) >= 1

        # Grid entity
        grid_ents = [e for e in scenario.entities if e.model == "Grid"]
        assert len(grid_ents) == 1
        assert grid_ents[0].params.get("gridfile") == "simple_four_bus_system"

        # Load entities from sndata active_mapping
        load_ents = [e for e in scenario.entities if e.model == "Load"]
        assert len(load_ents) == 2  # bus 2 and bus 3

    def test_inheritance(self):
        parser = MidasScenarioParser()

        import yaml
        raw = yaml.safe_load(SAMPLE_SCENARIO)

        # Use the parser's internal method
        all_scenarios = parser._parse_all_dict(raw)
        der_scenario = [s for s in all_scenarios if s.name == "test_scenario_der"][0]

        # Should inherit modules from parent + own modules
        assert "weather" in der_scenario.modules
        assert "der" in der_scenario.modules
        # Should inherit powergrid_params from parent
        assert "powergrid_params" in der_scenario.raw or \
               any("powergrid" in k for k in der_scenario.simulators)

    def test_expr_evaluation(self):
        parser = MidasScenarioParser()
        assert parser._eval_expr("1*24*60*60") == 86400
        assert parser._eval_expr("15*60") == 900
        assert parser._eval_expr(3600) == 3600

    def test_missing_file_raises(self):
        parser = MidasScenarioParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path.yml")


# ── Adapter Tests ────────────────────────────────────────────────────────────
class TestMidasSimulationAdapter:
    def test_to_gui_dict(self, scenario_file: Path):
        adapter = MidasSimulationAdapter()
        scenario = adapter.parse(scenario_file)
        mapped = adapter.map(scenario)
        gui_dict = adapter.to_gui_dict(mapped)

    record_metric("midas_gui_simulators", float(len(gui_dict.get("simulators", {}) or {})), "count")
    record_metric("midas_gui_entities", float(len(gui_dict.get("entities", []) or [])), "count")
    record_metric("midas_gui_connections", float(len(gui_dict.get("connections", []) or [])), "count")

    assert "name" in gui_dict
    assert "simulators" in gui_dict
    assert "entities" in gui_dict
    assert "connections" in gui_dict
    assert isinstance(gui_dict["simulators"], dict)
    assert isinstance(gui_dict["entities"], list)

    def test_parse_and_map_roundtrip(self, scenario_file: Path):
        adapter = MidasSimulationAdapter()
        scenario = adapter.parse(scenario_file)
        mapped = adapter.map(scenario)
        gui_dict = adapter.to_gui_dict(mapped)

        record_metric("midas_gui_simulators", float(len(gui_dict.get("simulators", {}) or {})), "count")
        record_metric("midas_gui_entities", float(len(gui_dict.get("entities", []) or [])), "count")
        record_metric("midas_gui_connections", float(len(gui_dict.get("connections", []) or [])), "count")

        assert gui_dict["duration"] == 86400
        assert gui_dict["step_size"] == 900
        assert len(gui_dict["simulators"]) > 0

    def test_list_available_scenarios(self, tmp_path: Path):
        """Test listing scenarios from a directory."""
        # Write a test scenario file
        (tmp_path / "test.yml").write_text(SAMPLE_SCENARIO, encoding="utf-8")

        adapter = MidasSimulationAdapter()
        results = adapter.list_available_scenarios(tmp_path)

        assert len(results) >= 1
        names = {r["name"] for r in results}
        assert "test_scenario" in names


# ── Mapper Tests ─────────────────────────────────────────────────────────────

class TestMidasToSallyMapper:
    def test_type_mapping(self):
        parser = MidasScenarioParser()
        mapper = MidasToSallyMapper()
        scenario = parser.parse_string(SAMPLE_SCENARIO, name="test")
        result = mapper.map(scenario)

        # Should have mapped powergrid module
        pg_sims = {k: v for k, v in result.simulators.items() if "powergrid" in k}
        assert len(pg_sims) > 0
        for sim in pg_sims.values():
            assert "powergrid" in sim.sally_module.lower()

    def test_attribute_translation(self):
        mapper = MidasToSallyMapper()
        # Attribute translation still works
        translated = mapper._translate_params({"p_mw": 1.0, "vm_pu": 0.98})
        assert "active_power_mw" in translated
        assert "voltage_pu" in translated

    def test_custom_type_registration(self):
        mapper = MidasToSallyMapper()
        mapper.register_type(
            "custom_module",
            "sally.custom.module",
            "CustomSim",
            "Custom",
        )

        parser = MidasScenarioParser()
        yaml_str = textwrap.dedent("""\
            custom_test:
              modules: [custom_module]
              end: 3600
              step_size: 900
              custom_module_params:
                scope1:
                  some_param: true
        """)
        scenario = parser.parse_string(yaml_str, name="custom_test")
        result = mapper.map(scenario)

        custom_sims = {k: v for k, v in result.simulators.items()
                       if "custom_module" in k}
        assert len(custom_sims) > 0
        for sim in custom_sims.values():
            assert sim.sally_module == "sally.custom.module"

    def test_unknown_module_falls_back(self):
        parser = MidasScenarioParser()
        mapper = MidasToSallyMapper()
        yaml_str = textwrap.dedent("""\
            fallback_test:
              modules: [totally_unknown]
              end: 3600
              step_size: 900
        """)
        scenario = parser.parse_string(yaml_str, name="fallback")
        result = mapper.map(scenario)

        assert len(result.simulators) > 0
        for sim in result.simulators.values():
            assert sim.sally_class == "Unknown"

    def test_metadata_includes_source(self, scenario_file: Path):
        parser = MidasScenarioParser()
        mapper = MidasToSallyMapper()
        scenario = parser.parse_file(scenario_file)
        result = mapper.map(scenario)

        assert "source" in result.metadata
        assert str(scenario_file) in result.metadata["source"]
