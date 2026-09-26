"""Read a bounded number of frames through the production RTSP adapter."""

from __future__ import annotations

import argparse
import uuid

from person_search.workers.sources import RtspFrameSource


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Credential-free, allowlisted RTSP URL")
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")

    source = RtspFrameSource(max_reconnects=2).open(args.url, camera_id=uuid.uuid4())
    with source:
        for count, frame in enumerate(source, start=1):
            if count == args.frames:
                print(
                    f"ok frames={count} last_index={frame.source_frame_index} "
                    f"last_timestamp_ms={frame.source_timestamp_ms} reconnects={source.reconnects}"
                )
                return


if __name__ == "__main__":
    main()
