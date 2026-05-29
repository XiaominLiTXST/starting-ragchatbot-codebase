import os
import sys

import pytest
from fastapi.testclient import TestClient

# Make backend modules importable when pytest runs from project root or within tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Make helpers importable from sibling test modules
sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_mock_rag, make_test_app


@pytest.fixture
def mock_rag():
    """Default mock RAGSystem with sensible return values."""
    return make_mock_rag()


@pytest.fixture
def client(mock_rag):
    """TestClient wired to the test app using the default mock RAGSystem."""
    return TestClient(make_test_app(mock_rag))


@pytest.fixture
def make_client():
    """
    Factory fixture — call make_client(rag=...) to get a TestClient backed by a
    custom mock RAGSystem.  Example::

        def test_error(make_client):
            rag = make_mock_rag(raise_on_query=RuntimeError("boom"))
            c = make_client(rag)
            assert c.post("/api/query", json={"query": "q"}).status_code == 500
    """
    def _factory(rag=None):
        return TestClient(make_test_app(rag))
    return _factory
