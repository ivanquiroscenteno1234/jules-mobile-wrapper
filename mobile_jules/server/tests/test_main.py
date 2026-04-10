import sys
from unittest.mock import MagicMock

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

import pytest
from unittest.mock import patch
import os

# Set dummy environment variables
os.environ["JULES_API_KEY"] = "dummy_key"

# We need to define some things that main.py expects from mocked modules
# e.g., BaseModel, FastAPI, etc.
class DummyBaseModel:
    def __init__(self, **kwargs):
        pass
    @classmethod
    def __init_subclass__(cls, **kwargs):
        pass

mock_pydantic.BaseModel = DummyBaseModel

from mobile_jules.server.main import decrypt_password

def test_decrypt_password_empty_token():
    assert decrypt_password("") == ""
    assert decrypt_password(None) is None

@patch("mobile_jules.server.main.cipher_suite", None)
def test_decrypt_password_no_cipher_suite():
    token = "some_token"
    assert decrypt_password(token) == token

def test_decrypt_password_success():
    mock_cipher = MagicMock()
    mock_cipher.decrypt.return_value = b"decrypted_password"

    with patch("mobile_jules.server.main.cipher_suite", mock_cipher):
        result = decrypt_password("encrypted_token")
        assert result == "decrypted_password"
        mock_cipher.decrypt.assert_called_once_with(b"encrypted_token")

def test_decrypt_password_failure_fallback():
    mock_cipher = MagicMock()
    mock_cipher.decrypt.side_effect = Exception("Decryption failed")

    token = "plain_text_token"
    with patch("mobile_jules.server.main.cipher_suite", mock_cipher):
        result = decrypt_password(token)
        assert result == token
        mock_cipher.decrypt.assert_called_once_with(token.encode())

from mobile_jules.server.main import encrypt_password

def test_encrypt_password_empty_password():
    assert encrypt_password("") == ""
    assert encrypt_password(None) is None

@patch("mobile_jules.server.main.cipher_suite", None)
def test_encrypt_password_no_cipher_suite():
    password = "some_password"
    assert encrypt_password(password) == password

def test_encrypt_password_success():
    mock_cipher = MagicMock()
    mock_cipher.encrypt.return_value = b"encrypted_password"

    with patch("mobile_jules.server.main.cipher_suite", mock_cipher):
        result = encrypt_password("plain_password")
        assert result == "encrypted_password"
        mock_cipher.encrypt.assert_called_once_with(b"plain_password")
