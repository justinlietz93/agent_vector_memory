"""
Pytest configuration and fixtures for vector memory tests.

Provides common test fixtures and setup for CLI testing.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for testing."""
    mock = Mock()
    mock.get_dimension.return_value = 1024
    mock.embed_text.return_value = [0.1] * 1024
    return mock


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    mock = Mock()
    mock.ensure_collection.return_value = {"status": "created"}
    mock.upsert.return_value = {"indexed": 1}
    mock.search.return_value = []
    return mock


@pytest.fixture
def temp_memory_bank():
    """Temporary directory with sample memory bank files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        memory_dir = Path(temp_dir) / "memory-bank"
        memory_dir.mkdir()

        # Create sample markdown files
        (memory_dir / "test1.md").write_text("# Test Memory 1\n\nThis is test content.")
        (memory_dir / "test2.md").write_text("# Test Memory 2\n\nMore test content.")
        (memory_dir / "nested").mkdir()
        (memory_dir / "nested" / "test3.md").write_text("# Nested Test\n\nNested content.")

        yield memory_dir


@pytest.fixture
def clean_environment():
    """Clean environment variables for testing."""
    env_vars_to_clean = [
        'MEMORY_COLLECTION_NAME',
        'MEMORY_COLLECTION_NAME_2',
        'MEMORY_COLLECTION_NAME_3',
        'QDRANT_URL',
        'OLLAMA_URL',
        'EMBED_MODEL'
    ]

    original_env = {}
    for var in env_vars_to_clean:
        if var in os.environ:
            original_env[var] = os.environ[var]
            del os.environ[var]

    yield

    # Restore original environment
    for var, value in original_env.items():
        os.environ[var] = value


@pytest.fixture
def sample_dotenv_content():
    """Sample .env file content for testing."""
    return """
# Vector Memory Configuration
MEMORY_COLLECTION_NAME=test_primary
MEMORY_COLLECTION_NAME_2=test_secondary
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
EMBED_MODEL=mxbai-embed-large

# Other variables
OTHER_VAR=should_be_ignored
"""


@pytest.fixture
def mock_qdrant_response():
    """Mock Qdrant collections response."""
    return {
        "result": {
            "collections": [
                {"name": "existing_collection_1"},
                {"name": "existing_collection_2"},
                {"name": "test_primary"}
            ]
        }
    }


# Test markers for categorizing tests
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "cli: mark test as CLI command test"
    )
    config.addinivalue_line(
        "markers", "env: mark test as environment resolution test"
    )


@pytest.fixture(autouse=True)
def reset_mocks():
    """Automatically reset all mocks after each test."""
    yield
    # This runs after each test - any cleanup can go here
    pass


class MockNamespace:
    """Helper class to create argparse.Namespace-like objects for testing."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return getattr(self.__dict__, name, None)


@pytest.fixture
def namespace_factory():
    """Factory for creating test namespace objects."""
    return MockNamespace
