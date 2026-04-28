"""conftest.py — Inject a mock bedrock_client before any project module is imported.

coordinator.py, specialists.py, and pipeline.py all do
`from bedrock_client import client, MODEL` at module level, which would try to
create an AnthropicBedrock session (requiring AWS credentials).  Replacing the
entire module in sys.modules here prevents any AWS call during tests.
"""
import sys
import os
import types
from unittest.mock import MagicMock

# Ensure the project root is on sys.path so project modules are importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Build a lightweight fake bedrock_client module.
_mock_client = MagicMock(name="bedrock_client.client")

_bedrock_mod = types.ModuleType("bedrock_client")
_bedrock_mod.client = _mock_client
_bedrock_mod.MODEL = "mock-model"
sys.modules["bedrock_client"] = _bedrock_mod
