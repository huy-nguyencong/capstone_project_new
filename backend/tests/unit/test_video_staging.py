import io
import subprocess
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

from person_search.api.errors import ApiError
from person_search.services.video_staging import VideoStaging

pytestmark = pytest.mark.unit


def test_rejects_forged_container_and_cleans(tmp_path):
    store = VideoStaging(tmp_path, reserve_bytes=0)
    with pytest.raises(ApiError) as error:
        store.stage(
            FileStorage(io.BytesIO(b"not a video"), filename="camera.mp4", content_type="video/mp4")
        )
    assert error.value.status == 415
    assert list(tmp_path.iterdir()) == []


def test_bounded_upload_and_low_disk(tmp_path, monkeypatch):
    store = VideoStaging(tmp_path, max_bytes=8, reserve_bytes=0)
    with pytest.raises(ApiError) as error:
        store.stage(FileStorage(io.BytesIO(b"x" * 9), filename="video.mp4"))
    assert error.value.status == 413
    store.max_bytes, store.reserve_bytes = 100, 10
    monkeypatch.setattr("shutil.disk_usage", lambda _: SimpleNamespace(free=10))
    with pytest.raises(ApiError) as error:
        store.stage(FileStorage(io.BytesIO(b"x"), filename="video.mp4"))
    assert error.value.status == 507
    assert list(tmp_path.iterdir()) == []


def test_interrupted_upload_cleans_partial_file(tmp_path):
    class BrokenStream:
        def read(self, size):
            raise OSError("connection interrupted")

    with pytest.raises(OSError):
        VideoStaging(tmp_path).stage(FileStorage(BrokenStream(), filename="video.mp4"))
    assert list(tmp_path.iterdir()) == []


def test_private_reference_and_no_symlink(tmp_path):
    store = VideoStaging(tmp_path)
    for value in ("../secret.mp4", "/tmp/secret.mp4", "video.exe"):
        with pytest.raises(ValueError):
            store.path(value)
    (tmp_path / "link.mp4").symlink_to(tmp_path / "outside.mp4")
    with pytest.raises(ValueError):
        store.path("link.mp4")


def test_probe_timeout_is_sanitized(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("private-path-secret", 10)

    monkeypatch.setattr(subprocess, "run", timeout)
    upload = FileStorage(io.BytesIO(b"\x00\x00\x00\x18ftypisom"), filename="video.mp4")
    with pytest.raises(ApiError) as error:
        VideoStaging(tmp_path, reserve_bytes=0).stage(upload)
    assert error.value.code == "unsupported_media"
    assert "secret" not in error.value.message
    assert list(tmp_path.iterdir()) == []
