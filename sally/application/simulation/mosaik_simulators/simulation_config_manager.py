#!/usr/bin/env python3
"""
Simulation Configuration Manager

This module provides a centralized configuration management system for Mosaik grid simulations.
It handles reading configuration from YAML files and provides access to all simulation parameters,
entity configurations, and connection settings.
"""

import yaml
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import os

from dependency_injector.wiring import inject

logger = logging.getLogger(__name__)


class SimulationConfigurationManager:
    """
    Centralized configuration manager for Mosaik grid simulations.

    This class manages all configuration data including:
    - Simulator configurations
    - Entity parameters and profiles
    - Connection settings
    - Simulation parameters
    - Logging configuration
    """
    @inject
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the configuration manager.

        Args:
            config_file: Path to YAML configuration file. If None, uses default.
        """
        self.config_file = config_file or self._get_default_config_path()
        self.config_data = {}
        self.sim_config = {}
        self.entity_configs = {}
        self.connection_pairs = []
        self.simulation_params = {}
        self.attribute_mappings = {}
        self.profiles = {}

        # Load configuration if file exists
        if self.config_file and os.path.exists(self.config_file):
            self.load_config()
        else:
            logger.warning(f"Config file not found: {self.config_file}. Using default configuration.")
            self._create_default_config()

    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        current_dir = Path(__file__).parent
        return str(current_dir / 'simulation_config.yml')

    def _create_default_config(self):
        """Create a default configuration structure."""
        self.config_data = {
            'simulators': {},
            'entities': {
                'nodes': {},
                'generators': {},
                'pv_systems': {},
                'loads': {},
                'lines': {},
                'batteries': {},
                'relays': {},
                'monitors': {},
                'remediation_controllers': {}
            },
            'connections': {'pairs': []},
            'simulation': {
                'duration': 100,
                'step_size': 1,
                'start_time': '2014-01-01 00:00:00'
            },
            'attributes': {},
            'profiles': {},
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        }

        self._build_sim_config()
        self._build_entity_configs()
        self._build_connection_pairs()
        self._build_simulation_params()
        self._build_attribute_mappings()
        self._build_profiles()

    def load_config(self, config_file: Optional[str] = None):
        """
        Load configuration from YAML file.

        Args:
            config_file: Path to configuration file. If None, uses instance config_file.
        """
        if config_file:
            self.config_file = config_file

        try:
            with open(self.config_file, 'r') as f:
                self.config_data = yaml.safe_load(f)

            # Build derived configurations
            self._build_sim_config()
            self._build_entity_configs()
            self._build_connection_pairs()
            self._build_simulation_params()
            self._build_attribute_mappings()
            self._build_profiles()

            logger.info(f"Configuration loaded successfully from {self.config_file}")

        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_file}: {e}")
            raise

    def save_config(self, config_file: Optional[str] = None):
        """
        Save current configuration to YAML file.

        Args:
            config_file: Path to save configuration. If None, uses instance config_file.
        """
        if config_file:
            self.config_file = config_file

        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Configuration saved to {self.config_file}")

        except Exception as e:
            logger.error(f"Failed to save configuration to {self.config_file}: {e}")
            raise

    def _build_sim_config(self):
        """Build Mosaik simulator configuration from loaded data."""
        simulators = self.config_data.get('simulators', {})

        self.sim_config = {}
        for sim_id, sim_info in simulators.items():
            python_class = sim_info.get('python_class', '')
            eid_prefix = sim_info.get('eid_prefix', sim_id[:3].capitalize())

            # Extract class name from full path
            if ':' in python_class:
                module_path, class_name = python_class.split(':')
                self.sim_config[sim_id] = {
                    'python': f'{module_path}:{class_name}',
                    'eid_prefix': eid_prefix
                }
            else:
                self.sim_config[sim_id] = {
                    'python': python_class,
                    'eid_prefix': eid_prefix
                }

    def _build_entity_configs(self):
        """Build entity configurations from loaded data."""
        entities = self.config_data.get('entities', {})

        self.entity_configs = {
            'nodes': entities.get('nodes', {}),
            'generators': entities.get('generators', {}),
            'pv_systems': entities.get('pv_systems', {}),
            'loads': entities.get('loads', {}),
            'lines': entities.get('lines', {}),
            'batteries': entities.get('batteries', {}),
            'relays': entities.get('relays', {}),
            'monitors': entities.get('monitors', {}),
            'remediation_controllers': entities.get('remediation_controllers', {})
        }

    def _build_connection_pairs(self):
        """Build connection pairs from loaded data."""
        connections = self.config_data.get('connections', {})
        self.connection_pairs = connections.get('pairs', [])

    def _build_simulation_params(self):
        """Build simulation parameters from loaded data."""
        simulation = self.config_data.get('simulation', {})
        self.simulation_params = {
            'duration': simulation.get('duration', 100),
            'step_size': simulation.get('step_size', 1),
            'start_time': simulation.get('start_time', '2014-01-01 00:00:00')
        }

    def _build_attribute_mappings(self):
        """Build attribute mappings from loaded data."""
        attributes = self.config_data.get('attributes', {})
        self.attribute_mappings = {
            'common': attributes.get('common', []),
            'generators': attributes.get('generators', []),
            'loads': attributes.get('loads', []),
            'lines': attributes.get('lines', []),
            'nodes': attributes.get('nodes', []),
            'batteries': attributes.get('batteries', []),
            'relays': attributes.get('relays', []),
            'monitors': attributes.get('monitors', []),
            'remediation': attributes.get('remediation', [])
        }

    def _build_profiles(self):
        """Build default profiles from loaded data."""
        profiles = self.config_data.get('profiles', {})
        self.profiles = {
            'default_irradiance': profiles.get('default_irradiance', []),
            'default_load_P': profiles.get('default_load_P', []),
            'default_load_Q': profiles.get('default_load_Q', [])
        }

    # Public API methods

    def get_sim_config(self) -> Dict[str, Dict[str, str]]:
        """Get Mosaik simulator configuration."""
        return self.sim_config

    def get_entity_config(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """
        Get configuration for a specific entity.

        Args:
            entity_type: Type of entity (nodes, generators, etc.)
            entity_id: ID of the entity

        Returns:
            Entity configuration dictionary
        """
        entities = self.entity_configs.get(entity_type, {})
        return entities.get(entity_id, {})

    def get_all_entities_of_type(self, entity_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all entities of a specific type.

        Args:
            entity_type: Type of entity (nodes, generators, etc.)

        Returns:
            Dictionary of entity configurations
        """
        return self.entity_configs.get(entity_type, {})

    def get_connection_pairs(self) -> List[List[str]]:
        """Get list of connection pairs."""
        return self.connection_pairs

    def get_simulation_params(self) -> Dict[str, Any]:
        """Get simulation parameters."""
        return self.simulation_params

    def get_attribute_mapping(self, entity_type: str) -> List[str]:
        """
        Get attribute mapping for a specific entity type.

        Args:
            entity_type: Type of entity

        Returns:
            List of attribute names
        """
        return self.attribute_mappings.get(entity_type, self.attribute_mappings.get('common', []))

    def get_profile(self, profile_name: str) -> List[float]:
        """
        Get a default profile by name.

        Args:
            profile_name: Name of the profile

        Returns:
            Profile data as list of floats
        """
        return self.profiles.get(profile_name, [])

    def get_logging_config(self) -> Dict[str, str]:
        """Get logging configuration."""
        return self.config_data.get('logging', {})

    def update_entity_config(self, entity_type: str, entity_id: str, config: Dict[str, Any]):
        """
        Update configuration for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            config: New configuration
        """
        if entity_type in self.entity_configs:
            self.entity_configs[entity_type][entity_id] = config
            self.config_data['entities'][entity_type][entity_id] = config

    def add_entity(self, entity_type: str, entity_id: str, config: Dict[str, Any]):
        """
        Add a new entity configuration.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            config: Entity configuration
        """
        if entity_type not in self.entity_configs:
            self.entity_configs[entity_type] = {}
            self.config_data['entities'][entity_type] = {}

        self.entity_configs[entity_type][entity_id] = config
        self.config_data['entities'][entity_type][entity_id] = config

    def add_connection_pair(self, source_sim: str, target_sim: str):
        """
        Add a connection pair.

        Args:
            source_sim: Source simulator ID
            target_sim: Target simulator ID
        """
        pair = [source_sim, target_sim]
        if pair not in self.connection_pairs:
            self.connection_pairs.append(pair)
            self.config_data['connections']['pairs'].append(pair)

    def set_simulation_duration(self, duration: int):
        """
        Set simulation duration.

        Args:
            duration: Simulation duration in time steps
        """
        self.simulation_params['duration'] = duration
        self.config_data['simulation']['duration'] = duration

    def get_config_summary(self) -> str:
        """Get a summary of the current configuration."""
        summary = f"""
Simulation Configuration Summary:
- Config file: {self.config_file}
- Simulators: {len(self.sim_config)} configured
- Entity types: {len(self.entity_configs)}
- Connection pairs: {len(self.connection_pairs)}
- Simulation duration: {self.simulation_params.get('duration', 'N/A')} steps
- Start time: {self.simulation_params.get('start_time', 'N/A')}
        """

        # Count entities by type
        for entity_type, entities in self.entity_configs.items():
            summary += f"- {entity_type}: {len(entities)} entities\n"

        return summary.strip()

    def validate_config(self) -> List[str]:
        """
        Validate the configuration for completeness and consistency.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check required sections
        required_sections = ['simulators', 'entities', 'connections', 'simulation']
        for section in required_sections:
            if section not in self.config_data:
                errors.append(f"Missing required section: {section}")

        # Check simulator configurations
        for sim_id, sim_config in self.sim_config.items():
            if 'python' not in sim_config:
                errors.append(f"Simulator {sim_id} missing python class configuration")

        # Check entity configurations
        for entity_type, entities in self.entity_configs.items():
            for entity_id, config in entities.items():
                if not config:
                    errors.append(f"Entity {entity_type}.{entity_id} has empty configuration")

        # Check connection pairs
        for pair in self.connection_pairs:
            if len(pair) != 2:
                errors.append(f"Invalid connection pair: {pair}")

        return errors

    def print_config_summary(self):
        """Print a summary of the current configuration."""
        print(self.get_config_summary())

        if self.connection_pairs:
            print("\nConnection pairs:")
            for i, pair in enumerate(self.connection_pairs, 1):
                print(f"  {i}. {pair[0]} -> {pair[1]}")

    def get_entity_creation_params(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """
        Get parameters needed to create a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            Dictionary of creation parameters
        """
        config = self.get_entity_config(entity_type, entity_id)

        # Add default profiles if not specified
        if entity_type == 'pv_systems' and 'irradiance_profile' not in config:
            config['irradiance_profile'] = self.get_profile('default_irradiance')

        if entity_type == 'loads':
            if 'base_P_MW_profile' not in config:
                config['base_P_MW_profile'] = self.get_profile('default_load_P')
            if 'base_Q_MVAR_profile' not in config:
                config['base_Q_MVAR_profile'] = self.get_profile('default_load_Q')

        return config

    def get_simulator_eid_prefix(self, sim_id: str) -> str:
        """
        Get the entity ID prefix for a simulator.

        Args:
            sim_id: Simulator ID

        Returns:
            Entity ID prefix
        """
        sim_info = self.config_data.get('simulators', {}).get(sim_id, {})
        return sim_info.get('eid_prefix', sim_id[:3].capitalize())