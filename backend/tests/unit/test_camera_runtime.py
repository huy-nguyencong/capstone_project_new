import subprocess
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from person_search.api.errors import ApiError
from person_search.services.camera_runtime import CameraRuntime

pytestmark = pytest.mark.unit


@pytest.fixture
def runtime():
    return CameraRuntime(Fernet.generate_key().decode(), ["10.0.0.0/8"])


def test_credentials_encrypted_and_roundtrip(runtime):
    url, secret = runtime.split_url("rtsp://admin:secret@10.0.0.1:554/live")
    assert url == "rtsp://10.0.0.1:554/live"
    assert "secret" not in secret
    assert runtime.cipher.decrypt(secret.encode()) == b"admin:secret"
    assert runtime.split_url(None) == (None, None)


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1",
        "rtsp://",
        "rtsp://host:bad/live",
        [],
        "rtsp://host/live?token=secret",
        "rtsp://host/\nstream",
    ],
)
def test_invalid_urls(runtime, url):
    with pytest.raises(ApiError) as error:
        runtime.split_url(url)
    assert error.value.code == "invalid_rtsp_url"


@pytest.mark.parametrize("host", ["127.0.0.1", "169.254.169.254", "example.com", "8.8.8.8"])
def test_allowlist_rejects_unapproved_hosts_without_network(runtime, host):
    with patch("subprocess.run") as run, pytest.raises(ApiError) as error:
        runtime.probe(f"rtsp://{host}/live", None)
    assert error.value.code == "rtsp_host_forbidden"
    run.assert_not_called()


def test_probe_timeout_and_missing_binary(runtime):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 10)) as run:
        assert runtime.probe("rtsp://10.0.0.1/live", None) == "OFFLINE"
        assert run.call_args.kwargs["timeout"] == 10
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert runtime.probe("rtsp://10.0.0.1/live", None) == "ERROR"
    with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"video\n")):
        assert runtime.probe("rtsp://10.0.0.1/live", None) == "ONLINE"


def test_missing_key_fails_closed():
    with pytest.raises(ApiError) as error:
        CameraRuntime().split_url("rtsp://admin:secret@10.0.0.1/live")
    assert error.value.code == "secret_store_unavailable"


def test_connection_url_rejects_embedded_credentials_before_network(runtime):
    with pytest.raises(ApiError) as error:
        runtime.connection_url("rtsp://admin:secret@10.0.0.1/live", None)
    assert error.value.code == "invalid_rtsp_url"
