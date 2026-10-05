"""Precompute the image token features of every READY track for ITM re-ranking.

Reads the tracks from PostgreSQL and their representative frames from MinIO with the settings of
``backend/.env``, crops each person exactly as the index did, runs the RaSa image encoder once
per track (about 1.3 s on the CPU) and stores the token features as float16 in the cache
directory that the application's re-ranking stage reads (``PERSON_SEARCH_ITM_TOKEN_CACHE``,
default ``var/cache/itm_tokens``). Tracks already in the cache are skipped, so the tool can be
interrupted and resumed.

    python tools/warm_itm_cache.py --registry config/models.example.json --artifact-root config \
        --settings config/rasa_cuhk_pedes_runtime.json
"""

from __future__ import annotations

import argparse
import io
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from sqlalchemy import select

from person_search.ai.encoders import RasaRuntimeFactory, load_rasa_settings
from person_search.ai.registry import load_registry
from person_search.config import StorageSettings
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import PersonTrack, TrackIndexStatus
from person_search.storage.runtime import StorageRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    load_dotenv()
    cache_dir = args.cache_dir or Path(
        os.getenv("PERSON_SEARCH_ITM_TOKEN_CACHE", "var/cache/itm_tokens")
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    import numpy as np

    settings = StorageSettings.from_environment()
    runtime = StorageRuntime.from_settings(settings)
    try:
        with runtime.postgres.session_factory() as session:
            rows = session.execute(
                select(
                    PersonTrack.id,
                    PersonTrack.minio_object_key,
                    PersonTrack.bbox_x,
                    PersonTrack.bbox_y,
                    PersonTrack.bbox_width,
                    PersonTrack.bbox_height,
                ).where(PersonTrack.index_status == TrackIndexStatus.READY)
            ).all()
        frames = MinioFrameStore(runtime.minio.client, settings.minio.bucket)
        registry = load_registry(
            args.registry,
            artifact_root=args.artifact_root,
            preflight_available={"rasa_cuhk_pedes_v1"},
        )
        assert registry.encoder is not None
        encoder = RasaRuntimeFactory(
            registry.encoder,
            artifact_root=args.artifact_root,
            settings=load_rasa_settings(args.settings),
        ).load()
        todo = [row for row in rows if not (cache_dir / f"{row[0]}.npy").is_file()]
        if args.limit:
            todo = todo[: args.limit]
        print(f"{len(rows)} ready tracks, {len(rows) - len(todo)} cached, {len(todo)} to compute")
        started = time.perf_counter()
        for index, (track_id, key, x, y, width, height) in enumerate(todo, start=1):
            if not key:
                continue
            content = frames.get_frame(key)
            with Image.open(io.BytesIO(content)) as frame:
                crop = frame.convert("RGB").crop((x, y, x + width, y + height))
            try:
                tokens = encoder.image_tokens(crop)[0].cpu().numpy().astype(np.float16)
            finally:
                crop.close()
            np.save(cache_dir / f"{track_id}.npy", tokens)
            if index % 50 == 0 or index == len(todo):
                elapsed = time.perf_counter() - started
                print(
                    f"  {index}/{len(todo)} in {elapsed:.0f} s ({elapsed / index:.2f} s per track)",
                    flush=True,
                )
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
