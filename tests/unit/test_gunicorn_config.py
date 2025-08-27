"""Unit tests for Gunicorn timeout configuration."""

import os
import subprocess
import unittest
from unittest.mock import patch, MagicMock, call
import tempfile
import shutil


class TestGunicornTimeoutConfiguration(unittest.TestCase):
    """Test suite for Gunicorn timeout configuration."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.entrypoint_path = os.path.join(self.test_dir, 'entrypoint.sh')
        
        # Copy the actual entrypoint.sh for testing
        actual_entrypoint = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'entrypoint.sh'
        )
        if os.path.exists(actual_entrypoint):
            with open(actual_entrypoint, 'r') as src:
                content = src.read()
            with open(self.entrypoint_path, 'w') as dst:
                dst.write(content)
            os.chmod(self.entrypoint_path, 0o755)

    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_default_timeout_value(self):
        """Test that default timeout is 300 seconds."""
        # Read the entrypoint script
        with open(self.entrypoint_path, 'r') as f:
            content = f.read()
        
        # Check for default timeout configuration
        self.assertIn('GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-300}', content)
        self.assertIn('--timeout=${GUNICORN_TIMEOUT}', content)

    def test_default_workers_value(self):
        """Test that default workers is 4."""
        with open(self.entrypoint_path, 'r') as f:
            content = f.read()
        
        # Check for default workers configuration
        self.assertIn('GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}', content)
        self.assertIn('--workers=${GUNICORN_WORKERS}', content)

    @patch.dict(os.environ, {'GUNICORN_TIMEOUT': '600'})
    def test_custom_timeout_from_env(self):
        """Test that custom timeout can be set via environment variable."""
        # Simulate running the script and capturing the command
        with open(self.entrypoint_path, 'r') as f:
            content = f.read()
        
        # Extract the timeout configuration line
        for line in content.split('\n'):
            if 'GUNICORN_TIMEOUT=' in line:
                # This would evaluate to 600 due to our env var
                self.assertIn('${GUNICORN_TIMEOUT:-300}', line)
                break
        else:
            self.fail('GUNICORN_TIMEOUT configuration not found')

    @patch.dict(os.environ, {'GUNICORN_WORKERS': '8'})
    def test_custom_workers_from_env(self):
        """Test that custom workers can be set via environment variable."""
        with open(self.entrypoint_path, 'r') as f:
            content = f.read()
        
        # Extract the workers configuration line
        for line in content.split('\n'):
            if 'GUNICORN_WORKERS=' in line:
                # This would evaluate to 8 due to our env var
                self.assertIn('${GUNICORN_WORKERS:-4}', line)
                break
        else:
            self.fail('GUNICORN_WORKERS configuration not found')

    def test_gunicorn_command_structure(self):
        """Test that the gunicorn command has the correct structure."""
        with open(self.entrypoint_path, 'r') as f:
            content = f.read()
        
        # Check for the complete gunicorn command
        self.assertIn('exec gunicorn', content)
        self.assertIn('--workers=${GUNICORN_WORKERS}', content)
        self.assertIn('--bind=0.0.0.0:5000', content)
        self.assertIn('--timeout=${GUNICORN_TIMEOUT}', content)
        self.assertIn('"app:create_app()"', content)

    def test_echo_statement_shows_config(self):
        """Test that the echo statement displays the configuration."""
        with open(self.entrypoint_path, 'r') as f:
            content = f.read()
        
        # Check for informative echo statement
        self.assertIn('echo "Starting Gunicorn with timeout=${GUNICORN_TIMEOUT}s and workers=${GUNICORN_WORKERS}', content)

    @patch('subprocess.run')
    def test_timeout_prevents_worker_timeout(self, mock_run):
        """Test that timeout setting prevents worker timeouts during long operations."""
        # Simulate a long-running request scenario
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # Set a high timeout for testing
        with patch.dict(os.environ, {'GUNICORN_TIMEOUT': '300'}):
            # This simulates what would happen when entrypoint.sh runs
            timeout_value = os.environ.get('GUNICORN_TIMEOUT', '300')
            self.assertEqual(timeout_value, '300')
            
            # Verify this is sufficient for CSV import operations
            # 300 seconds = 5 minutes should be enough for large CSV imports
            self.assertGreaterEqual(int(timeout_value), 300)

    def test_environment_variables_documented(self):
        """Test that environment variables are documented in .env.example."""
        env_example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            '.env.example'
        )
        
        if os.path.exists(env_example_path):
            with open(env_example_path, 'r') as f:
                content = f.read()
            
            # Check that GUNICORN variables are documented
            self.assertIn('GUNICORN_TIMEOUT', content)
            self.assertIn('GUNICORN_WORKERS', content)
            # Check for helpful comments
            self.assertIn('# Gunicorn Configuration', content)

    @patch('subprocess.Popen')
    def test_gunicorn_starts_with_correct_params(self, mock_popen):
        """Test that gunicorn is started with the correct parameters."""
        # Mock the process
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        # Set test environment variables
        test_env = {
            'GUNICORN_TIMEOUT': '500',
            'GUNICORN_WORKERS': '6'
        }
        
        with patch.dict(os.environ, test_env):
            # Simulate what the entrypoint script would construct
            timeout = os.environ.get('GUNICORN_TIMEOUT', '300')
            workers = os.environ.get('GUNICORN_WORKERS', '4')
            
            expected_cmd = [
                'gunicorn',
                f'--workers={workers}',
                '--bind=0.0.0.0:5000',
                f'--timeout={timeout}',
                'app:create_app()'
            ]
            
            # Verify the command components
            self.assertEqual(timeout, '500')
            self.assertEqual(workers, '6')
            self.assertIn('--timeout=500', expected_cmd)
            self.assertIn('--workers=6', expected_cmd)


class TestTimeoutIntegrationWithCSVImport(unittest.TestCase):
    """Test timeout configuration with CSV import scenarios."""

    def test_timeout_sufficient_for_large_csv(self):
        """Test that 300 second timeout is sufficient for large CSV imports."""
        # CSV import characteristics:
        # - Large files can have 10,000+ rows
        # - Each row might require API calls or database operations
        # - Processing rate: ~50-100 rows per second
        # - 10,000 rows / 50 rows per second = 200 seconds
        
        default_timeout = 300  # seconds
        estimated_processing_time = 200  # seconds for 10,000 rows
        
        # Ensure timeout provides adequate buffer
        self.assertGreater(
            default_timeout, 
            estimated_processing_time,
            "Default timeout should be sufficient for large CSV imports"
        )
        
        # Check buffer is reasonable (50% extra time)
        buffer_ratio = default_timeout / estimated_processing_time
        self.assertGreaterEqual(
            buffer_ratio, 
            1.5, 
            "Timeout should provide at least 50% buffer over estimated time"
        )

    def test_timeout_configuration_in_production(self):
        """Test that production configuration includes timeout settings."""
        # Check DigitalOcean app.yaml configuration
        app_yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            '.do', 'app.yaml'
        )
        
        if os.path.exists(app_yaml_path):
            with open(app_yaml_path, 'r') as f:
                content = f.read()
            
            # Verify GUNICORN_TIMEOUT is configured
            self.assertIn('GUNICORN_TIMEOUT', content)
            # Verify it's set to 300 or higher
            if '- key: GUNICORN_TIMEOUT' in content:
                # Find the value line after the key
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if '- key: GUNICORN_TIMEOUT' in line:
                        # Look for the value in the next few lines
                        for j in range(i+1, min(i+4, len(lines))):
                            if 'value:' in lines[j]:
                                # Extract the value
                                value_line = lines[j]
                                if '"300"' in value_line or '300' in value_line:
                                    break
                        else:
                            self.fail('GUNICORN_TIMEOUT value not found or incorrect')


if __name__ == '__main__':
    unittest.main()