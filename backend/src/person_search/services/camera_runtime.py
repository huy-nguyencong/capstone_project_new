"""Private RTSP credentials and bounded, allowlisted RTSP probes."""

import ipaddress
import os
import subprocess
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken

from person_search.api.errors import ApiError


class CameraRuntime:
    def __init__(self, key=None, networks=()):
        self.cipher = Fernet(key.encode()) if key else None
        self.networks = tuple(ipaddress.ip_network(n.strip()) for n in networks if n.strip())

    @classmethod
    def from_environment(cls):
        return cls(
            os.getenv("PERSON_SEARCH_RTSP_KEY"),
            os.getenv("PERSON_SEARCH_RTSP_NETWORKS", "").split(","),
        )

    def split_url(self, value):
        if value is None or value == "":
            return None, None
        try:
            if (
                not isinstance(value, str)
                or len(value) > 2048
                or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
            ):
                raise ValueError
            url = urlsplit(value)
            if url.scheme not in {"rtsp", "rtsps"} or not url.hostname or url.fragment:
                raise ValueError
            if url.port is not None and url.port < 1:
                raise ValueError
            # Credentials in query strings cannot be safely classified; reject all queries.
            if url.query:
                raise ValueError
            host = url.netloc.rsplit("@", 1)[-1]
            public = urlunsplit((url.scheme, host, url.path, "", ""))
        except (ValueError, TypeError):
            raise ApiError(422, "invalid_rtsp_url", "Địa chỉ RTSP không hợp lệ.") from None
        secret = None
        if "@" in url.netloc:
            if not self.cipher:
                raise ApiError(503, "secret_store_unavailable", "Chưa cấu hình khóa bảo vệ RTSP.")
            secret = self.cipher.encrypt(url.netloc.rsplit("@", 1)[0].encode()).decode()
        return public, secret

    def probe(self, url, secret):
        parsed = urlsplit(url)
        try:
            address = ipaddress.ip_address(parsed.hostname)
            if (
                address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_unspecified
                or not any(address in n for n in self.networks)
            ):
                raise ValueError
        except ValueError:
            raise ApiError(
                422,
                "rtsp_host_forbidden",
                "RTSP test cần địa chỉ IP thuộc mạng camera được cho phép.",
            ) from None
        if secret:
            try:
                credentials = self.cipher.decrypt(secret.encode()).decode() if self.cipher else None
                if credentials is None:
                    raise ValueError
                url = urlunsplit(parsed._replace(netloc=credentials + "@" + parsed.netloc))
            except (InvalidToken, ValueError):
                raise ApiError(
                    503, "secret_store_unavailable", "Không đọc được cấu hình RTSP."
                ) from None
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-rtsp_transport",
                    "tcp",
                    "-rw_timeout",
                    "8000000",
                    "-protocol_whitelist",
                    "tcp,tls,rtsp,rtsps",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "csv=p=0",
                    url,
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            return "ONLINE" if result.returncode == 0 and b"video" in result.stdout else "OFFLINE"
        except subprocess.TimeoutExpired:
            return "OFFLINE"
        except OSError:
            return "ERROR"
