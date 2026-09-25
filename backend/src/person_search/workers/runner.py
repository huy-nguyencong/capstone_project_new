"""One globally serialized worker, with leases and deterministic crash replay."""

from sqlalchemy import text

from person_search.storage.postgres.models import (
    AIConfigVersion,
    Camera,
    JobStatus,
    TrackIndexStatus,
)
from person_search.workers.pipeline import VideoFrameSource

WORKER_LOCK = 734202


class JobCancelled(Exception):
    pass


class WorkerStopped(Exception):
    pass


class VideoWorker:
    def __init__(self, engine, jobs, pipeline_factory, ingestion_factory, source=None, stop=None):
        self.engine, self.jobs = engine, jobs
        self.pipeline_factory, self.ingestion_factory = pipeline_factory, ingestion_factory
        self.source = source or VideoFrameSource()
        self.stop = stop or (lambda: False)

    def run_once(self):
        # Session lock is held through all ingestion; expired lease alone cannot permit overlap.
        with self.engine.connect() as guard:
            if not guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}):
                return False
            guard.commit()
            try:
                self.jobs.cleanup()
                job = self.jobs.claim()
                if job is None:
                    return False
                self.process(job, guard)
                return True
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})
                guard.commit()

    def process(self, job, guard):
        pipeline = None
        stage = "pipeline_unavailable"
        try:
            if job.attempts > 3:
                self.jobs.finish(
                    job.id, job.lease_token, JobStatus.FAILED, "worker_retries_exhausted"
                )
                return
            with self.jobs.factory() as work:
                config = work.session.get(AIConfigVersion, job.ai_config_version_id)
                area_id = work.session.get(Camera, job.camera_id).area_id
                pipeline = self.pipeline_factory(config)
                ingestion = self.ingestion_factory(config)
            sampled = 0
            processed = 0

            def checkpoint():
                # Confirm the connection owning our global lock is alive before side effects.
                guard.execute(text("SELECT 1"))
                if self.stop():
                    raise WorkerStopped
                if not self.jobs.checkpoint(job.id, job.lease_token, processed, sampled):
                    raise JobCancelled

            def publish(track):
                nonlocal stage
                checkpoint()
                stage = "encoder_failed"
                request = pipeline.request(job, area_id, track)
                stage = "storage_ingestion_failed"
                result = ingestion.ingest_track(request)
                if result.status == TrackIndexStatus.PENDING:
                    result = ingestion.resume(request.track_id)
                if result.status != TrackIndexStatus.READY:
                    raise RuntimeError("Track did not reach READY")

            checkpoint()
            stage = "video_decode_failed"
            for frame in self.source.frames(
                self.jobs.staging.path(job.source_ref), job.sampling_interval
            ):
                processed = frame.index + 1
                checkpoint()
                if frame.image is not None:
                    sampled += 1
                    stage = "detector_failed"
                    boxes = pipeline.detector.detect(frame)
                    stage = "tracker_failed"
                    for track in pipeline.tracker.update(frame, boxes):
                        publish(track)
                stage = "video_decode_failed"
            stage = "tracker_failed"
            for track in pipeline.tracker.finish():
                publish(track)
            checkpoint()
            if processed == 0:
                raise ValueError("No video frames")
            self.jobs.finish(job.id, job.lease_token, JobStatus.SUCCEEDED)
        except WorkerStopped:
            pass  # Leave lease for crash-safe replay after graceful shutdown.
        except JobCancelled:
            self.jobs.finish(job.id, job.lease_token, JobStatus.CANCELLED)
        except Exception:
            # Error details may contain paths, credentials or model internals. Store only the stage.
            self.jobs.finish(job.id, job.lease_token, JobStatus.FAILED, stage)
        finally:
            if pipeline is not None:
                pipeline.tracker.close()
