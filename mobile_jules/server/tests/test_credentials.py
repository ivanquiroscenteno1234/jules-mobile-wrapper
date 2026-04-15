import sys
import json
import os
from unittest.mock import MagicMock, patch, mock_open

# Mock dependencies properly for FastAPI and Pydantic
mock_fastapi = MagicMock()
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.middleware.cors"] = MagicMock()

mock_pydantic = MagicMock()
sys.modules["pydantic"] = mock_pydantic

# Mock other dependencies
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["httpx"] = MagicMock()

# Mock cryptography
mock_fernet_mod = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.fernet"] = mock_fernet_mod
mock_fernet_mod.Fernet.generate_key.return_value = b"dummy_key_32_bytes_long_exactly_32"

# Mock internal modules
sys.modules["jules_client"] = MagicMock()
sys.modules["notifications"] = MagicMock()
sys.modules["tester_agent"] = MagicMock()
sys.modules["github_client"] = MagicMock()

# Set dummy environment variables
os.environ["JULES_API_KEY"] = "dummy_key"

# We need to define some things that main.py expects from mocked modules
class DummyBaseModel:
    def __init__(self, **kwargs):
        pass
    @classmethod
    def __init_subclass__(cls, **kwargs):
        pass

mock_pydantic.BaseModel = DummyBaseModel

from mobile_jules.server.main import save_credentials, load_credentials, CREDENTIALS_FILE

def test_save_credentials_success():
    data = {"repo/name": [{"id": "1", "name": "test"}]}
    m = mock_open()
    with patch("builtins.open", m):
        save_credentials(data)

    m.assert_called_once_with(CREDENTIALS_FILE, "w")
    handle = m()
    # Check that json.dump was called. json.dump calls handle.write multiple times because of indent
    written_data = "".join(call.args[0] for call in handle.write.call_args_list)
    assert json.loads(written_data) == data

def test_load_credentials_file_not_found():
    with patch("os.path.exists", return_value=False):
        result = load_credentials()
        assert result == {}

def test_load_credentials_success():
    data = {"repo/name": [{"id": "1", "name": "test"}]}
    m = mock_open(read_data=json.dumps(data))
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", m):
            result = load_credentials()
            assert result == data
    m.assert_called_once_with(CREDENTIALS_FILE, "r")

def test_load_credentials_invalid_json():
    m = mock_open(read_data="invalid json")
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", m):
            result = load_credentials()
            assert result == {}
