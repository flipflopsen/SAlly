import h5py
from tkinter import filedialog, messagebox
from collections import defaultdict


class HDF5Parser:
    def __init__(self, filepath=None):
        self.filepath = filepath
        # Stores {'EntityName': ['Var1', 'Var2'], ...}
        self._discovered_entity_to_variables_map = defaultdict(list)

    def _clear_discovered_items(self):
        self._discovered_entity_to_variables_map = defaultdict(list)

    def _visitor_function(self, name, obj):
        if isinstance(obj, h5py.Dataset):
            path_parts = name.split('/')
            if len(path_parts) >= 2:
                entity_name = path_parts[-2]
                variable_name = path_parts[-1]
                if variable_name not in self._discovered_entity_to_variables_map[entity_name]:
                    self._discovered_entity_to_variables_map[entity_name].append(variable_name)


    def discover_structure_from_file(self, filepath=None):
        """
        Opens the HDF5 file and traverses it to build a map of
        {EntityName: [Variable1, Variable2, ...]}.
        Returns this dictionary.
        """
        if filepath:
            self.filepath = filepath

        if not self.filepath:
            print("Error: No HDF5 filepath provided to parser for discovery.")
            return {}  # Return empty dict

        self._clear_discovered_items()

        try:
            with h5py.File(self.filepath, 'r') as hf:
                hf.visititems(self._visitor_function)
        except FileNotFoundError:
            # Propagate error or handle in GUI:
            # messagebox.showerror("Error", f"HDF5 file not found: {self.filepath}")
            print(f"Error: HDF5 file not found: {self.filepath}")
            return {}
        except Exception as e:
            # messagebox.showerror("Error", f"Error reading HDF5 file '{self.filepath}': {e}")
            print(f"Error reading HDF5 file '{self.filepath}': {e}")
            return {}

        # Convert defaultdict to regular dict for return and sort variable lists
        return_map = {}
        for entity, variables in self._discovered_entity_to_variables_map.items():
            return_map[entity] = sorted(variables)
        return return_map

    # get_data_snapshot method remains useful for evaluation later, no change needed here for discovery
    def get_data_snapshot(self, entity_name: str, variable_name: str, timestep_index: int):
        if not self.filepath:
            return None
        # This path construction needs to be robust for your HDF5 structure
        possible_paths_to_dataset = [f"{entity_name}/{variable_name}"]  # Adapt as needed
        try:
            with h5py.File(self.filepath, 'r') as hf:
                dataset_obj = None
                for path_try in possible_paths_to_dataset:
                    if path_try in hf:
                        dataset_obj = hf[path_try]
                        break
                if dataset_obj is not None and isinstance(dataset_obj, h5py.Dataset):
                    if 0 <= timestep_index < len(dataset_obj):
                        return dataset_obj[timestep_index]
        except Exception as e:
            print(f"Error accessing HDF5 data for {entity_name}/{variable_name}: {e}")
        return None
