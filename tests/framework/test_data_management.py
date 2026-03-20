import os
from pathlib import Path


class TestDataManager:
    """Manages test data files from a predefined directory"""

    _test_data_dir = None

    @classmethod
    def set_test_data_directory(cls, test_data_path: str):
        """Set the test data directory path"""
        test_path = Path(test_data_path)
        if not test_path.exists():
            # Start from current absolute path
            current_path = Path.cwd().resolve()
            last_folder = test_path.parts[-1] if test_path.parts else None
            if last_folder is None:
                raise FileNotFoundError(f"Invalid test data path: {test_data_path}")

            # Try up to 5 directories back
            found = False
            for _ in range(5):
                candidate = current_path / last_folder
                if candidate.exists() and candidate.is_dir():
                    test_path = candidate
                    found = True
                    break
                current_path = current_path.parent

            if not found:
                raise FileNotFoundError(f"Test data directory not found in reverse search: {test_data_path}")

        cls._test_data_dir = str(test_path.absolute())

    @classmethod
    def get_test_file_path(cls, filename: str) -> str:
        """Get absolute path to test file"""
        if cls._test_data_dir is None:
            raise ValueError("Test data directory not set. Call set_test_data_directory() first.")

        file_path = Path(cls._test_data_dir) / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Test file does not exist: {file_path}")

        return str(file_path)

    @classmethod
    def get_test_data_dir(cls) -> str:
        """Get the test data directory path"""
        if cls._test_data_dir is None:
            raise ValueError("Test data directory not set. Call set_test_data_directory() first.")
        return cls._test_data_dir


class FilePathInterceptor:
    """Intercepts file path operations to redirect to test data"""

    # Define mapping of production file paths to test file names
    FILE_MAPPINGS = {
        'config/sally.yml': 'test_config.yml',
        'simulation/test_data/demo.hdf5': 'test_simulation.hdf5',
        'data/input.csv': 'test_input.csv',
        # Add more mappings as needed
    }

    @classmethod
    def patch_file_operations(cls):
        """Patch common file operations to use test data"""
        original_open = open
        original_exists = os.path.exists
        original_isfile = os.path.isfile

        def patched_open(filename, *args, **kwargs):
            redirected_path = cls._get_redirected_path(filename)
            return original_open(redirected_path, *args, **kwargs)

        def patched_exists(path):
            redirected_path = cls._get_redirected_path(path)
            return original_exists(redirected_path)

        def patched_isfile(path):
            redirected_path = cls._get_redirected_path(path)
            return original_isfile(redirected_path)

        # Apply patches
        import builtins
        builtins.open = patched_open
        os.path.exists = patched_exists
        os.path.isfile = patched_isfile

        # Store originals for restoration
        cls._original_open = original_open
        cls._original_exists = original_exists
        cls._original_isfile = original_isfile

    @classmethod
    def restore_file_operations(cls):
        """Restore original file operations"""
        if hasattr(cls, '_original_open'):
            import builtins
            builtins.open = cls._original_open
            os.path.exists = cls._original_exists
            os.path.isfile = cls._original_isfile

    @classmethod
    def _get_redirected_path(cls, original_path):
        """Get redirected path for test file"""
        # Normalize path separators
        normalized_path = original_path.replace('\\', '/')

        # Check if path matches any of our mappings
        for prod_path, test_file in cls.FILE_MAPPINGS.items():
            if normalized_path.endswith(prod_path) or normalized_path == prod_path:
                try:
                    return TestDataManager.get_test_file_path(test_file)
                except (ValueError, FileNotFoundError):
                    # If test file not found, return original path
                    break

        return original_path
