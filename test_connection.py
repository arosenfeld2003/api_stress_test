"""Unit tests for the _load_env function in src.db.connection module."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open


class TestLoadEnv(unittest.TestCase):
    """Test cases for _load_env function."""

    def setUp(self):
        """Store original environment state before each test."""
        self.original_env = os.environ.copy()

    def tearDown(self):
        """Restore original environment state after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        # Remove the module from cache to force reimport for each test
        if "src.db.connection" in sys.modules:
            del sys.modules["src.db.connection"]

    @patch("src.db.connection.load_dotenv")
    @patch("src.db.connection.Path")
    def test_load_env_from_cwd(self, mock_path_class, mock_load_dotenv):
        """Test that _load_env loads variables from .env in current working directory."""
        # Arrange
        mock_root_env = MagicMock()
        mock_root_env.exists.return_value = False
        
        mock_file_path = MagicMock()
        mock_file_path.resolve.return_value.parents = [Path("/fake"), Path("/")]
        
        mock_path_class.return_value = mock_root_env
        mock_path_class.__truediv__ = lambda self, other: mock_root_env
        
        with patch("src.db.connection.__file__", "/fake/src/db/connection.py"):
            mock_path_instance = MagicMock()
            mock_path_instance.resolve.return_value.parents = {
                0: Path("/fake/src/db"),
                1: Path("/fake/src"),
                2: Path("/fake")
            }
            mock_path_class.return_value = mock_path_instance
            
            # Act
            from src.db.connection import _load_env
            _load_env()
        
        # Assert - first call is from CWD upward
        self.assertEqual(mock_load_dotenv.call_count, 1)
        first_call = mock_load_dotenv.call_args_list[0]
        self.assertEqual(first_call[1]["override"], False)

    @patch("src.db.connection.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="TEST_VAR=from_root\n")
    def test_load_env_from_repo_root(self, mock_file, mock_load_dotenv):
        """Test that _load_env loads variables from .env in repository root."""
        # Arrange
        repo_root = Path("/Users/alexrosenfeld/qwasar_mscs_25-26/api_stress_test")
        root_env_path = repo_root / ".env"
        
        def path_side_effect(arg):
            if arg == root_env_path:
                mock_path = MagicMock(spec=Path)
                mock_path.exists.return_value = True
                return mock_path
            return Path(arg)
        
        with patch("src.db.connection.Path") as mock_path_class:
            mock_file_obj = MagicMock()
            mock_file_obj.resolve.return_value.parents = {
                2: repo_root
            }
            mock_path_class.return_value = mock_file_obj
            mock_path_class.side_effect = lambda x: x if isinstance(x, Path) else Path(x)
            
            # Mock __file__ to point to the connection.py location
            with patch("src.db.connection.__file__", str(repo_root / "src" / "db" / "connection.py")):
                # Act
                from src.db.connection import _load_env
                _load_env()
        
        # Assert - should be called at least once for CWD
        self.assertGreaterEqual(mock_load_dotenv.call_count, 1)
        # Verify override=False is used
        for call in mock_load_dotenv.call_args_list:
            self.assertEqual(call[1]["override"], False)

    @patch("src.db.connection.load_dotenv")
    @patch("src.db.connection.Path")
    def test_load_env_does_not_override_existing(self, mock_path_class, mock_load_dotenv):
        """Test that _load_env does not override existing environment variables."""
        # Arrange
        os.environ["TEST_VAR"] = "existing_value"
        
        mock_root_env = MagicMock()
        mock_root_env.exists.return_value = False
        mock_path_class.return_value = mock_root_env
        
        # Act
        from src.db.connection import _load_env
        _load_env()
        
        # Assert - override=False should be passed to load_dotenv
        for call in mock_load_dotenv.call_args_list:
            self.assertEqual(call[1]["override"], False)
        
        # Verify original environment variable is unchanged
        self.assertEqual(os.environ["TEST_VAR"], "existing_value")

    @patch("src.db.connection.load_dotenv", side_effect=Exception("File read error"))
    @patch("src.db.connection.Path")
    def test_load_env_handles_exceptions_gracefully(self, mock_path_class, mock_load_dotenv):
        """Test that _load_env handles exceptions gracefully during environment file loading."""
        # Arrange
        mock_root_env = MagicMock()
        mock_root_env.exists.return_value = True
        mock_path_class.return_value = mock_root_env
        
        # Act - should not raise an exception
        try:
            from src.db.connection import _load_env
            _load_env()
            exception_raised = False
        except Exception:
            exception_raised = True
        
        # Assert - no exception should be raised (fail-open behavior)
        self.assertFalse(exception_raised)

    @patch("src.db.connection.load_dotenv")
    @patch("src.db.connection.Path")
    def test_load_env_no_env_files_present(self, mock_path_class, mock_load_dotenv):
        """Test that _load_env correctly functions when no .env files are present."""
        # Arrange
        mock_root_env = MagicMock()
        mock_root_env.exists.return_value = False
        
        mock_file_path = MagicMock()
        mock_file_path.resolve.return_value.parents = {2: Path("/fake")}
        
        mock_path_class.return_value = mock_root_env
        with patch("src.db.connection.__file__", "/fake/src/db/connection.py"):
            mock_path_class.side_effect = lambda x: mock_file_path if x == "/fake/src/db/connection.py" else mock_root_env
            
            # Act
            from src.db.connection import _load_env
            _load_env()
        
        # Assert - should still call load_dotenv for CWD search
        self.assertGreaterEqual(mock_load_dotenv.call_count, 1)
        # Should use override=False
        self.assertEqual(mock_load_dotenv.call_args_list[0][1]["override"], False)


if __name__ == "__main__":
    unittest.main()
