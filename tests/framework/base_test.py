import io
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Callable, Dict
from unittest.mock import MagicMock

import numpy as np

from tests.framework.assertions import SimulationAssertion
from tests.framework.dataclasses import SimulationTrace, SimulationStep
from tests.framework.env_conf import TestConfiguration
from tests.framework.test_builder import SimulationTestBuilder


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class BaseSimulationTest(unittest.TestCase):
    """Base test class for simulation tests"""

    @classmethod
    def setUpClass(cls):
        test_data_directory = str((Path(__file__).resolve().parents[1] / "test_data"))
        TestConfiguration.setup_test_environment(test_data_directory)

    @classmethod
    def tearDownClass(cls):
        TestConfiguration.cleanup_test_environment()

    def setUp(self):
        self.simulation_trace = SimulationTrace()
        self.test_builder = SimulationTestBuilder()
        self.assertions = []
        self.container = None
        self.original_providers = {}
        self.temp_files = []

    def tearDown(self):
        self.test_builder.cleanup()

        # Clean up container if used
        if self.container:
            for provider_name, original_provider in self.original_providers.items():
                getattr(self.container, provider_name).reset_override()
            self.container.unwire()

    def add_assertion(self, assertion: SimulationAssertion):
        self.assertions.append(assertion)

    @contextmanager
    def _suppress_stdout(self):
        """Context manager to suppress stdout"""
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            yield
        finally:
            sys.stdout = old_stdout

    def _print_test_header(self, test_name: str):
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}🧪 Running Test: {test_name}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")

    def _print_test_info(self, simulation):
        print(f"{Colors.OKCYAN}📊 Test Configuration:{Colors.ENDC}")
        print(f"   • Total timesteps: {Colors.BOLD}{simulation.total_timesteps}{Colors.ENDC}")
        print(f"   • Entities: {Colors.BOLD}{len(simulation.entity_variable_timeseries_data)}{Colors.ENDC}")
        print(f"   • Relations: {Colors.BOLD}{len(simulation.relation_data)}{Colors.ENDC}")
        print(f"   • Rules configured: {Colors.BOLD}{len(self.test_builder.mock_rules)}{Colors.ENDC}")

    def _print_simulation_progress(self, current_step: int, total_steps: int):
        if current_step % max(1, total_steps // 10) == 0 or current_step == total_steps - 1:
            progress = (current_step + 1) / total_steps * 100
            bar_length = 30
            filled_length = int(bar_length * (current_step + 1) // total_steps)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            print(
                f"\r{Colors.OKBLUE}⚡ Simulation Progress: |{bar}| {progress:.1f}% ({current_step + 1}/{total_steps}){Colors.ENDC}",
                end='')
        if current_step == total_steps - 1:
            print()

    def run_simulation_test(self, test_name: str, setup_func: Optional[Callable] = None):
        self._print_test_header(test_name)

        if setup_func:
            setup_func(self.test_builder)

        _ = self.test_builder.build_hdf5_file() if self.test_builder.hdf5_builder else "test_simulation.hdf5"

        mocks = self._build_dependency_mocks()

        if hasattr(self, 'setup_container_with_mocks'):
            self.setup_container_with_mocks({'rule_manager': mocks['rule_manager']})

        try:
            _ = self._build_mock_h5py_file()

            # Import the real SmartGridSimulation for now (path is under application/simulation)
            from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation

            # Suppress all simulator output
            with self._suppress_stdout():
                simulation = SmartGridSimulation(_, mocks['rule_manager'])
                simulation.total_timesteps = self.test_builder.hdf5_builder.get_total_timesteps()
                simulation.entity_variable_timeseries_data = self.test_builder.hdf5_builder.data
                simulation.relation_data = self.test_builder.hdf5_builder.relations

                # Add test rules
                for rule in self.test_builder.mock_rules:
                    simulation.rule_manager.add_rule_from_gui_dict(rule)

                # Check & set timesteps if set manually
                if self.test_builder.maximum_timesteps > 0:
                    simulation.total_timesteps = self.test_builder.maximum_timesteps

            self._print_test_info(simulation)

            print(f"\n{Colors.OKBLUE}🚀 Starting simulation execution...{Colors.ENDC}")

            # Capture execution (suppress simulator output)
            with self._suppress_stdout():
                self._capture_simulation_execution(simulation)
                simulation.close()

            self.simulation_trace.success = True
            print(f"{Colors.OKGREEN}✅ Simulation completed successfully!{Colors.ENDC}")

        except Exception as e:
            self.simulation_trace.success = False
            self.simulation_trace.error_message = str(e)
            print(f"{Colors.FAIL}❌ Simulation error: {e}{Colors.ENDC}")
            raise

        self._run_assertions()

    def _build_mock_h5py_file(self) -> MagicMock:
        """Build a mock h5py.File that simulates the real HDF5 structure"""
        data = self._get_hdf5_data()
        return self._create_mock_h5py_file(data)

    def _get_hdf5_data(self) -> Dict:
        """Extract HDF5 data from test builder"""
        if not self.test_builder.hdf5_builder or not self.test_builder.hdf5_builder.data:
            return {}
        return self.test_builder.hdf5_builder.data

    def _create_mock_h5py_file(self, data: Dict) -> MagicMock:
        """Create mock HDF5 file from data dictionary"""
        mock_file = MagicMock()

        if not data:
            mock_file.visititems.side_effect = lambda visitor_func: None
            mock_file.close.return_value = None
            mock_file.attrs = {}
            return mock_file

        mock_datasets = {}

        # Create mock datasets for entity data
        for entity_name, variables in data.items():
            if entity_name == 'Relations':
                continue
            for variable_name, dataset_data in variables.items():
                dataset_path = f"{entity_name}/{variable_name}"
                mock_datasets[dataset_path] = self._create_mock_dataset(dataset_data)

        # Create mock datasets for Relations data
        if 'Relations' in data:
            for relation_name, relation_data in data['Relations'].items():
                dataset_path = f"Relations/{relation_name}"
                mock_datasets[dataset_path] = self._create_mock_dataset(relation_data)

        def mock_visititems(visitor_func):
            """Mock the HDF5 visititems functionality"""
            for path, dataset in mock_datasets.items():
                try:
                    visitor_func(path, dataset)
                except Exception as e:
                    print(f"Error in visititems for {path}: {e}")

        mock_file.visititems.side_effect = mock_visititems
        mock_file.close.return_value = None
        mock_file.attrs = {}

        return mock_file

    def _create_mock_dataset(self, data) -> MagicMock:
        """Create a mock HDF5 dataset with proper behavior"""
        mock_dataset = MagicMock()

        # Ensure data is numpy array
        if not isinstance(data, np.ndarray):
            data = np.array(data)

        # Mock dataset behavior properly
        mock_dataset.__getitem__.side_effect = lambda idx: data[idx] if isinstance(idx, (int, slice)) else data
        mock_dataset.__len__.return_value = len(data)
        mock_dataset.shape = data.shape
        mock_dataset.dtype = data.dtype

        return mock_dataset

    def _build_dependency_mocks(self) -> Dict[str, MagicMock]:
        """Build mocks for simulation dependencies"""
        mocks = {}

        mock_rule_manager = MagicMock()
        mock_rule_manager.rules = []

        def add_rule_side_effect(rule_dict):
            mock_rule_manager.rules.append(rule_dict)

        def evaluate_rules_side_effect(current_data):
            triggered = []
            for rule in self.test_builder.mock_rules:
                entity_data = current_data.get(rule.get("entity_name", ""), {})
                actual_val = entity_data.get(rule.get("variable_name", ""))

                if (rule.get("operator") == "LESS_THAN" and
                        actual_val is not None and
                        float(actual_val) < float(rule.get("value", 0))):
                    triggered.append({
                        "action_command": rule.get("action"),
                        "triggering_rule_id": rule.get("id"),
                        "triggering_entity": rule.get("entity_name"),
                        "triggering_variable": rule.get("variable_name"),
                        "triggering_value": actual_val,
                        "rule_operator": rule.get("operator"),
                        "rule_threshold": rule.get("value")
                    })
            return triggered

        mock_rule_manager.add_rule_from_gui_dict.side_effect = add_rule_side_effect
        mock_rule_manager.evaluate_rules_at_timestep.side_effect = evaluate_rules_side_effect
        mocks['rule_manager'] = mock_rule_manager

        return mocks

    def _capture_simulation_execution(self, simulation):
        """Sim-Executing method with capture/state functionality"""
        if simulation.total_timesteps == 0:
            print(f"{Colors.WARNING}⚠️  Warning: No timesteps found in simulation{Colors.ENDC}")
            return

        step_count = 0
        while step_count < simulation.total_timesteps:
            # Update progress
            self._print_simulation_progress(step_count, simulation.total_timesteps)

            # Get current data before stepping
            current_data = simulation.get_current_data_snapshot()

            # Evaluate rules with current data
            triggered_rules = []
            if hasattr(simulation, 'rule_manager') and simulation.rule_manager:
                triggered_rules = simulation.rule_manager.evaluate_rules_at_timestep(current_data)

            # Create simulation step record
            simulation_step = SimulationStep(
                step_number=step_count,
                input_data=current_data,
                output_data=current_data,
                triggered_rules=triggered_rules
            )
            self.simulation_trace.steps.append(simulation_step)
            self.simulation_trace.total_steps += 1

            # Advance simulation
            if not simulation.step():
                break

            step_count += 1

    def _run_assertions(self):
        """Run all configured assertions with verbose output"""
        print(f"\n{Colors.OKCYAN}🔍 Running {len(self.assertions)} assertion(s)...{Colors.ENDC}")

        passed_assertions = 0
        failed_assertions = 0

        for i, assertion in enumerate(self.assertions, 1):
            assertion_name = assertion.__class__.__name__

            with self.subTest(assertion=assertion_name):
                try:
                    result = assertion.assert_condition(self.simulation_trace)

                    if result:
                        passed_assertions += 1
                        print(f"   {Colors.OKGREEN}✅ [{i}] {assertion_name}: PASSED{Colors.ENDC}")

                        if hasattr(assertion, 'get_success_details'):
                            details = assertion.get_success_details(self.simulation_trace)
                            print(f"      {Colors.OKCYAN}ℹ️  {details}{Colors.ENDC}")

                    else:
                        failed_assertions += 1
                        error_msg = assertion.get_error_message(self.simulation_trace)
                        print(f"   {Colors.FAIL}❌ [{i}] {assertion_name}: FAILED{Colors.ENDC}")
                        print(f"      {Colors.FAIL}💥 {error_msg}{Colors.ENDC}")

                    self.assertTrue(result, assertion.get_error_message(self.simulation_trace))

                except Exception as e:
                    failed_assertions += 1
                    print(f"   {Colors.FAIL}💥 [{i}] {assertion_name}: ERROR{Colors.ENDC}")
                    print(f"      {Colors.FAIL}🚨 {str(e)}{Colors.ENDC}")
                    raise

        # Print summary
        print(f"\n{Colors.BOLD}📋 Assertion Summary:{Colors.ENDC}")
        print(f"   {Colors.OKGREEN}✅ Passed: {passed_assertions}{Colors.ENDC}")
        if failed_assertions > 0:
            print(f"   {Colors.FAIL}❌ Failed: {failed_assertions}{Colors.ENDC}")
        else:
            print(f"   {Colors.FAIL}❌ Failed: 0{Colors.ENDC}")

        total_steps = len(self.simulation_trace.steps)
        print(f"   {Colors.OKCYAN}📊 Total simulation steps: {total_steps}{Colors.ENDC}")

        if passed_assertions == len(self.assertions) and failed_assertions == 0:
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.ENDC}")
        else:
            print(f"\n{Colors.FAIL}{Colors.BOLD}❌ SOME TESTS FAILED ❌{Colors.ENDC}")
