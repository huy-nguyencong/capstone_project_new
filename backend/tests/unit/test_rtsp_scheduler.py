from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from person_search.services.rtsp_scheduler import (
    CameraCandidate,
    RtspSchedulerSettings,
    choose_camera,
)
from person_search.storage.postgres.models import JobStatus

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
COOLDOWN = timedelta(minutes=5)


def candidate(code, *, last=None, status=None, ended=None):
    return CameraCandidate(uuid.uuid4(), code, last, status, ended)


def test_never_served_camera_goes_first_then_least_recent():
    fresh = candidate("CAM-C")
    old = candidate("CAM-A", last=NOW - timedelta(hours=2), status=JobStatus.SUCCEEDED)
    recent = candidate("CAM-B", last=NOW - timedelta(minutes=1), status=JobStatus.SUCCEEDED)
    chosen = choose_camera([recent, old, fresh], now=NOW, failure_cooldown=COOLDOWN)
    assert chosen == fresh.camera_id
    assert choose_camera([recent, old], now=NOW, failure_cooldown=COOLDOWN) == old.camera_id


def test_ties_are_broken_by_camera_code():
    second, first = candidate("CAM-2"), candidate("CAM-1")
    assert choose_camera([second, first], now=NOW, failure_cooldown=COOLDOWN) == first.camera_id


def test_recently_failed_camera_waits_for_cooldown():
    failed = candidate(
        "CAM-A",
        last=NOW - timedelta(minutes=3),
        status=JobStatus.FAILED,
        ended=NOW - timedelta(minutes=2),
    )
    assert choose_camera([failed], now=NOW, failure_cooldown=COOLDOWN) is None
    later = NOW + timedelta(minutes=4)
    assert choose_camera([failed], now=later, failure_cooldown=COOLDOWN) == failed.camera_id


def test_no_candidates_means_no_session():
    assert choose_camera([], now=NOW, failure_cooldown=COOLDOWN) is None


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("PERSON_SEARCH_RTSP_AUTO", "0")
    monkeypatch.setenv("PERSON_SEARCH_RTSP_SESSION_FRAMES", "900")
    monkeypatch.setenv("PERSON_SEARCH_RTSP_FAILURE_COOLDOWN_SECONDS", "60")
    settings = RtspSchedulerSettings.from_environment()
    assert settings.enabled is False
    assert settings.session_frames == 900
    assert settings.failure_cooldown == timedelta(seconds=60)
    monkeypatch.setenv("PERSON_SEARCH_RTSP_SESSION_FRAMES", "0")
    with pytest.raises(ValueError):
        RtspSchedulerSettings.from_environment()
