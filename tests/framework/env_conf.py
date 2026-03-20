import os

from tests.framework.test_data_management import TestDataManager, FilePathInterceptor


class TestConfiguration:
    """Configuration for test environment"""

    @classmethod
    def setup_test_environment(cls, test_data_dir: str):
        """Setup complete test environment"""
        # Set test data directory
        TestDataManager.set_test_data_directory(test_data_dir)

        # Patch file operations
        FilePathInterceptor.patch_file_operations()

        # Set environment variables
        os.environ['TEST_MODE'] = 'true'
        os.environ['TEST_DATA_DIR'] = TestDataManager.get_test_data_dir()

    @classmethod
    def cleanup_test_environment(cls):
        """Cleanup test environment"""
        # Restore file operations
        FilePathInterceptor.restore_file_operations()

        # Clean environment variables
        os.environ.pop('TEST_MODE', None)
        os.environ.pop('TEST_DATA_DIR', None)
