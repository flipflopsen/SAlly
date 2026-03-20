"""
HDF5 Builder Module

Advanced HDF5 builder for simulation testing with multiple modes:
- REAL_HDF5: Use existing HDF5 file
- MANUAL_HDF5: Create from scratch with provided data
- HYBRID_HDF5: Modify existing HDF5 file
- RANDOM_HDF5: Generate random test data
"""

import tempfile
import os
import h5py
import numpy as np
import random
from enum import Enum
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import shutil

from sally.core.logger import get_logger

logger = get_logger(__name__)


class HDF5Mode(Enum):
    REAL_HDF5 = "real"
    MANUAL_HDF5 = "manual"
    HYBRID_HDF5 = "hybrid"
    RANDOM_HDF5 = "random"


class HDF5Builder:
    """Advanced HDF5 builder for simulation testing with multiple modes."""

    def __init__(self, mode: HDF5Mode, path: Optional[str] = None):
        self.mode = mode
        self.path = path
        self.data = {}  # For manual or hybrid mode data storage
        self.relations = {}  # For storing relation data
        self.temp_files = []  # Track temporary files for cleanup
        self.modifications = {}  # Track modifications for hybrid mode
        self.total_timesteps = 0

        # Validate initial configuration
        if self.mode == HDF5Mode.REAL_HDF5 and not path:
            raise ValueError("Path must be provided for REAL_HDF5 mode")
        if self.mode == HDF5Mode.HYBRID_HDF5 and not path:
            raise ValueError("Path to existing file must be provided for HYBRID_HDF5 mode")

        logger.info("HDF5Builder initialized: mode=%s path=%s", mode.value, path)

    def _load_hdf5_data(self):
        """Load data from HDF5 file."""
        if not self.path:
            logger.error("HDF5 filepath not provided for simulation")
            return

        self._entity_variable_timeseries_data = {}
        self._relation_data = {}
        self.total_timesteps = 0

        logger.debug("Loading HDF5 data from: %s", self.path)

        try:
            self._hdf5_file_handle = h5py.File(self.path, 'r')
            entities_loaded = 0
            variables_loaded = 0
            relations_loaded = 0

            def visitor_function(name, obj):
                nonlocal entities_loaded, variables_loaded, relations_loaded
                # name is the full HDF5 path, e.g., "Relations/CSV-0.PV_0" or "Generator1/P_MW_out"
                path_parts = name.split('/')

                if isinstance(obj, h5py.Dataset):
                    if path_parts[0] == "Relations" and len(path_parts) == 2:
                        # This is a relation dataset, e.g., Relations/CSV-0.PV_0
                        relation_name = path_parts[1]
                        self.relations[relation_name] = obj[:]  # Load the entire matrix/data
                        relations_loaded += 1
                        logger.debug("Loaded relation: %s shape=%s", relation_name, obj.shape)

                    elif path_parts[0] != "Relations":  # Process as potential "Series" data
                        # This part relies on your previously working "Series" parsing logic.
                        # Assuming EntityName/VariableName structure for series:
                        if len(path_parts) >= 2:
                            entity_name = path_parts[-2]
                            variable_name = path_parts[-1]

                            # Prevent misinterpreting something like "OtherGroup/Relations/Dataset"
                            if entity_name == "Relations":
                                return  # Skip if the immediate parent group is "Relations"

                            if entity_name not in self.data:
                                self.data[entity_name] = {}
                                entities_loaded += 1

                            self.data[entity_name][variable_name] = obj[:]
                            variables_loaded += 1

                            # Determine total_timesteps from Series data
                            current_len = len(obj[:])
                            if current_len > 0:
                                if self.total_timesteps == 0:
                                    self.total_timesteps = current_len

            self._hdf5_file_handle.visititems(visitor_function)

            if self.data and self.total_timesteps == 0:
                logger.warning("Series data found but total_timesteps is 0 (all datasets might be empty)")
            elif self.data:
                logger.info(
                    "HDF5 loaded: entities=%d variables=%d timesteps=%d relations=%d",
                    entities_loaded, variables_loaded, self.total_timesteps, relations_loaded
                )

            if not self.relations:
                logger.debug("No Relations data found in HDF5")

        except FileNotFoundError:
            logger.error("HDF5 file not found: %s", self.path)
            self.total_timesteps = 0
        except Exception as e:
            logger.exception("Error loading HDF5 file '%s': %s", self.path, e)
            self.total_timesteps = 0
        # File handle remains open for potential future partial reads (though currently all is loaded)
        # It will be closed by self.close()
        self._hdf5_file_handle.close()
        logger.debug("HDF5 file handle closed")

    def set_path(self, path: str) -> 'HDF5Builder':
        """Set the HDF5 file path."""
        if self.mode not in (HDF5Mode.REAL_HDF5, HDF5Mode.HYBRID_HDF5):
            raise ValueError("Setting path is only allowed in REAL_HDF5 or HYBRID_HDF5 modes")
        if self.mode == HDF5Mode.HYBRID_HDF5:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File {path} does not exist for HYBRID_HDF5 mode")
        self.path = path
        logger.debug("Path set: %s", path)
        return self

    def add_entity(self, entity_name: str, variables: Dict[str, List[Union[float, int]]]) -> 'HDF5Builder':
        """Add an entity with variables to the builder."""
        if self.mode not in (HDF5Mode.MANUAL_HDF5, HDF5Mode.HYBRID_HDF5):
            raise ValueError("Adding entities is only allowed in MANUAL_HDF5 or HYBRID_HDF5 modes")
        if entity_name not in self.data:
            self.data[entity_name] = {}
        for var_name, timeseries in variables.items():
            self.data[entity_name][var_name] = np.array(timeseries)
        if self.mode == HDF5Mode.HYBRID_HDF5:
            self.modifications[f"add_entity_{entity_name}"] = variables
        logger.debug("Entity added: %s variables=%d", entity_name, len(variables))
        return self

    def add_variable_to_entity(self, entity_name: str, variable_name: str,
                               timeseries: List[Union[float, int]]) -> 'HDF5Builder':
        if self.mode not in (HDF5Mode.MANUAL_HDF5, HDF5Mode.HYBRID_HDF5):
            raise ValueError("Adding variables is only allowed in MANUAL_HDF5 or HYBRID_HDF5 modes")
        if entity_name not in self.data:
            self.data[entity_name] = {}
        self.data[entity_name][variable_name] = np.array(timeseries)
        if self.mode == HDF5Mode.HYBRID_HDF5:
            self.modifications[f"add_var_{entity_name}_{variable_name}"] = timeseries
        return self

    def add_relation(self, relation_name: str, relation_data: Union[np.ndarray, List[List]]) -> 'HDF5Builder':
        if self.mode not in (HDF5Mode.MANUAL_HDF5, HDF5Mode.HYBRID_HDF5):
            raise ValueError("Adding relations is only allowed in MANUAL_HDF5 or HYBRID_HDF5 modes")
        self.relations[relation_name] = np.array(relation_data)
        if 'Relations' not in self.data:
            self.data['Relations'] = {}
        self.data['Relations'][relation_name] = np.array(relation_data)
        if self.mode == HDF5Mode.HYBRID_HDF5:
            self.modifications[f"add_relation_{relation_name}"] = relation_data
        return self

    def remove_entity(self, entity_name: str) -> 'HDF5Builder':
        if self.mode != HDF5Mode.HYBRID_HDF5:
            raise ValueError("Removing entities is only allowed in HYBRID_HDF5 mode")
        if entity_name in self.data:
            del self.data[entity_name]
        self.modifications[f"remove_entity_{entity_name}"] = True
        return self

    def remove_variable(self, entity_name: str, variable_name: str) -> 'HDF5Builder':
        if self.mode != HDF5Mode.HYBRID_HDF5:
            raise ValueError("Removing variables is only allowed in HYBRID_HDF5 mode")
        if entity_name in self.data and variable_name in self.data[entity_name]:
            del self.data[entity_name][variable_name]
        self.modifications[f"remove_var_{entity_name}_{variable_name}"] = True
        return self

    def modify_entity_data(self, entity_name: str, variable_name: str,
                           new_timeseries: List[Union[float, int]]) -> 'HDF5Builder':
        if self.mode != HDF5Mode.HYBRID_HDF5:
            raise ValueError("Modifying data is only allowed in HYBRID_HDF5 mode")
        if entity_name not in self.data:
            self.data[entity_name] = {}
        self.data[entity_name][variable_name] = np.array(new_timeseries)
        self.modifications[f"modify_{entity_name}_{variable_name}"] = new_timeseries
        return self

    def add_mosaik_style_entity(self, entity_type: str, entity_id: str,
                                attributes: Dict[str, List[Union[float, int]]]) -> 'HDF5Builder':
        entity_name = f"{entity_type}-{entity_id}"
        return self.add_entity(entity_name, attributes)

    def build(self) -> str:
        """Build the HDF5 file based on the configured mode."""
        logger.info("Building HDF5: mode=%s", self.mode.value)

        if self.mode == HDF5Mode.REAL_HDF5:
            if not self.path:
                raise ValueError("Path must be set for REAL_HDF5 mode")
            if not os.path.exists(self.path):
                raise FileNotFoundError(f"Real HDF5 file {self.path} does not exist")
            self._load_hdf5_data()
            logger.info("REAL_HDF5 loaded: %s", self.path)
            return self.path
        elif self.mode == HDF5Mode.MANUAL_HDF5:
            path = self._create_manual_hdf5()
            self.path = path
            self._load_hdf5_data()
            logger.info("MANUAL_HDF5 created: %s", path)
            return path
        elif self.mode == HDF5Mode.HYBRID_HDF5:
            path = self._create_hybrid_hdf5()
            self.path = path
            self._load_hdf5_data()
            logger.info("HYBRID_HDF5 created: %s", path)
            return path
        elif self.mode == HDF5Mode.RANDOM_HDF5:
            path = self._create_random_hdf5()
            self.path = path
            self._load_hdf5_data()
            logger.info("RANDOM_HDF5 created: %s entities=%d", path, len(self.data))
            return path
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def _create_manual_hdf5(self) -> str:
        """Create a manual HDF5 file from provided data."""
        temp_fd, temp_path = tempfile.mkstemp(suffix='.hdf5', prefix='manual_test_')
        os.close(temp_fd)
        self.temp_files.append(temp_path)
        logger.debug("Creating manual HDF5: %s", temp_path)
        try:
            with h5py.File(temp_path, 'w') as f:
                entities_written = 0
                for entity_name, variables in self.data.items():
                    if entity_name == 'Relations':
                        continue
                    entity_group = f.create_group(entity_name)
                    for var_name, timeseries_data in variables.items():
                        entity_group.create_dataset(var_name, data=timeseries_data)
                    entities_written += 1
                if self.relations:
                    relations_group = f.create_group('Relations')
                    for relation_name, relation_data in self.relations.items():
                        relations_group.create_dataset(relation_name, data=relation_data)
                f.attrs['created_by'] = 'HDF5Builder_Manual'
                f.attrs['mode'] = 'manual'
            logger.debug("Manual HDF5 created: entities=%d relations=%d", entities_written, len(self.relations))
        except Exception as e:
            logger.exception("Failed to create manual HDF5: %s", e)
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise RuntimeError(f"Failed to create manual HDF5 file: {e}")
        return temp_path

    def _create_hybrid_hdf5(self) -> str:
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Base file {self.path} does not exist")
        temp_fd, temp_path = tempfile.mkstemp(suffix='.hdf5', prefix='hybrid_test_')
        os.close(temp_fd)
        self.temp_files.append(temp_path)
        try:
            shutil.copy2(self.path, temp_path)
            with h5py.File(temp_path, 'a') as f:
                for mod_key in self.modifications:
                    if mod_key.startswith('remove_entity_'):
                        entity_name = mod_key.replace('remove_entity_', '')
                        if entity_name in f:
                            del f[entity_name]
                    elif mod_key.startswith('remove_var_'):
                        parts = mod_key.replace('remove_var_', '').split('_', 1)
                        if len(parts) == 2:
                            entity_name, var_name = parts
                            if entity_name in f and var_name in f[entity_name]:
                                del f[entity_name][var_name]
                for entity_name, variables in self.data.items():
                    if entity_name == 'Relations':
                        continue
                    if entity_name not in f:
                        entity_group = f.create_group(entity_name)
                    else:
                        entity_group = f[entity_name]
                    for var_name, timeseries_data in variables.items():
                        if var_name in entity_group:
                            del entity_group[var_name]
                        entity_group.create_dataset(var_name, data=timeseries_data)
                if self.relations:
                    if 'Relations' not in f:
                        relations_group = f.create_group('Relations')
                    else:
                        relations_group = f['Relations']
                    for relation_name, relation_data in self.relations.items():
                        if relation_name in relations_group:
                            del relations_group[relation_name]
                        relations_group.create_dataset(relation_name, data=relation_data)
                #f.attrs['modified_by'] = 'HDF5Builder_Hybrid'
                #f.attrs['original_file'] = self.path
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise RuntimeError(f"Failed to create hybrid HDF5 file: {e}")
        return temp_path

    def _create_random_hdf5(self) -> str:
        temp_fd, temp_path = tempfile.mkstemp(suffix='.hdf5', prefix='random_test_')
        os.close(temp_fd)
        self.temp_files.append(temp_path)
        self.data = {}
        self.relations = {}
        try:
            with h5py.File(temp_path, 'w') as f:
                num_entities = random.randint(2, 5)
                num_timesteps = random.randint(10, 30)
                self.total_timesteps = num_timesteps
                for i in range(num_entities):
                    entity_name = f"RandomEntity_{i}"
                    entity_group = f.create_group(entity_name)
                    self.data[entity_name] = {}
                    for var in ['P', 'Q', 'V']:
                        data = np.random.rand(num_timesteps) * 100
                        entity_group.create_dataset(var, data=data)
                        self.data[entity_name][var] = data
                # Relations (optional)
                num_relations = random.randint(1, 3)
                if num_relations > 0:
                    relations_group = f.create_group('Relations')
                    for j in range(num_relations):
                        relation_name = f"Rel_{j}"
                        matrix = np.random.randint(0, 2, size=(num_entities, num_entities))
                        relations_group.create_dataset(relation_name, data=matrix)
                        self.relations[relation_name] = matrix
                f.attrs['created_by'] = 'HDF5Builder_Random'
                f.attrs['mode'] = 'random'
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise RuntimeError(f"Failed to create random HDF5 file: {e}")
        return temp_path

    def get_total_timesteps(self) -> int:
        """Get the total number of timesteps in the data."""
        return self.total_timesteps

    def cleanup(self):
        """Clean up temporary files created by the builder."""
        logger.info("Cleaning up %d temporary files", len(self.temp_files))
        cleaned = 0
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    cleaned += 1
                except Exception as e:
                    logger.warning("Could not clean up %s: %s", temp_file, e)
        self.temp_files.clear()
        logger.debug("Cleanup complete: removed=%d", cleaned)
