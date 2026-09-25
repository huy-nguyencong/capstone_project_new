"""Bounded private video upload staging; filenames never come from the client."""

import errno
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from person_search.api.errors import ApiError


@dataclass(frozen=True)
class StagedVideo:
    name: str
    digest: str
    total_frames: int | None


class VideoStaging:
    def __init__(self, root, max_bytes=500 * 1024 * 1024, reserve_bytes=1024 * 1024 * 1024):
        if max_bytes <= 0 or reserve_bytes < 0:
            raise ValueError("Video max bytes must be positive and reserve nonnegative")
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes
        self.reserve_bytes = reserve_bytes

    @classmethod
    def from_environment(cls):
        return cls(
            os.getenv("PERSON_SEARCH_VIDEO_STAGING", "var/videos"),
            int(os.getenv("PERSON_SEARCH_VIDEO_MAX_BYTES", 500 * 1024 * 1024)),
            int(os.getenv("PERSON_SEARCH_VIDEO_RESERVE_BYTES", 1024 * 1024 * 1024)),
        )

    def path(self, name):
        if Path(name).name != name or not name.endswith((".mp4", ".mkv", ".avi")):
            raise ValueError("Invalid staging reference")
        path = self.root / name
        if path.is_symlink():
            raise ValueError("Symlink staging references are forbidden")
        return path

    def remove(self, name):
        self.path(name).unlink(missing_ok=True)

    def stage(self, upload):
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in {".mp4", ".mkv", ".avi"}:
            raise ApiError(415, "unsupported_media", "Chỉ nhận video MP4, MKV hoặc AVI.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = uuid.uuid4().hex + suffix
        path = self.path(name)
        digest, size = hashlib.sha256(), 0
        try:
            with path.open("xb") as destination:
                os.chmod(path, 0o600)
                while chunk := upload.stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ApiError(413, "file_too_large", "Video vượt giới hạn dung lượng.")
                    if shutil.disk_usage(self.root).free - len(chunk) < self.reserve_bytes:
                        raise ApiError(
                            507, "insufficient_storage", "Không đủ dung lượng lưu video."
                        )
                    destination.write(chunk)
                    digest.update(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            frames = self.inspect(path, suffix)
            return StagedVideo(name, digest.hexdigest(), frames)
        except BaseException as error:
            path.unlink(missing_ok=True)
            if isinstance(error, OSError) and error.errno in {errno.ENOSPC, errno.EDQUOT}:
                raise ApiError(
                    507, "insufficient_storage", "Không đủ dung lượng lưu video."
                ) from None
            raise

    def inspect(self, path, suffix):
        with path.open("rb") as stream:
            header = stream.read(16)
        signatures = {
            ".mp4": header[4:8] == b"ftyp",
            ".mkv": header[:4] == b"\x1aE\xdf\xa3",
            ".avi": header[:4] == b"RIFF" and header[8:12] == b"AVI ",
        }
        if not signatures[suffix]:
            raise ApiError(415, "unsupported_media", "Nội dung không khớp định dạng video.")
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-protocol_whitelist",
                    "file",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,nb_frames:format=format_name",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            metadata = json.loads(probe.stdout)
            stream = metadata["streams"][0]
            expected = {".mp4": "mp4", ".mkv": "matroska", ".avi": "avi"}[suffix]
            if (
                probe.returncode
                or expected not in metadata["format"]["format_name"]
                or not 0 < stream["width"] * stream["height"] <= 3840 * 2160
            ):
                raise ValueError
            decode = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file",
                    "-i",
                    str(path),
                    "-map",
                    "0:v:0",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            if decode.returncode:
                raise ValueError
            count = stream.get("nb_frames")
            return int(count) if count and count.isdecimal() and int(count) > 0 else None
        except FileNotFoundError:
            raise ApiError(
                503, "video_probe_unavailable", "Máy chủ chưa cài ffmpeg/ffprobe."
            ) from None
        except (ValueError, KeyError, IndexError, TypeError, subprocess.TimeoutExpired):
            raise ApiError(
                415, "unsupported_media", "Video không đọc được hoặc quá giới hạn kiểm tra."
            ) from None
