# scheduler_utils.py  (patched)
import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import SCHED_HOURS, SCHED_TEST_MODE  # add SCHED_TEST_MODE=True for testing if desired
from drive_utils import build_drive_service, pick_random_video_from_folder, download_drive_file_to_spooled
from youtube_utils import build_youtube_service, upload_video_from_fileobj
from tags_utils import fetch_trending_hashtags
from auth_utils import load_credentials
from flask import current_app

logger = logging.getLogger('scheduler_utils')
logging.getLogger('apscheduler').setLevel(logging.INFO)

class AutoUploader:
    def __init__(self, app=None):
        self.app = app
        self.scheduler = BackgroundScheduler()
        self.job = None
        self.folder_id = None
        self.region = None

    def init_app(self, app):
        """Register app and ensure scheduler starts only in the proper process."""
        self.app = app

        # If using Flask debug reloader, only start scheduler in the reloader child process.
        if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            logger.info("App in debug mode and not in reloader child; scheduler will not start here.")
            return

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

        # Optionally attach shutdown hook
        @app.teardown_appcontext
        def shutdown_scheduler(exc):
            if self.scheduler.running:
                # do not shutdown here on every request; only if app itself is stopping
                # (this handler is safest-in-practice but only called on app context teardown)
                pass

    def start(self, folder_id, region='US', run_immediately=False):
        """Start the recurring job.
        - folder_id: Drive folder to pick from
        - region: For trending hashtags
        - run_immediately: if True schedule first run now (useful for testing)
        """
        self.folder_id = folder_id
        self.region = region

        if self.job:
            self.stop()

        # Decide interval trigger unit: use hours normally; support test mode minutes
        if getattr(__import__('config'), 'SCHED_TEST_MODE', False):
            trigger = IntervalTrigger(minutes=SCHED_HOURS)
            logger.info("Using minutes trigger (test mode). Interval: %s minutes", SCHED_HOURS)
        else:
            trigger = IntervalTrigger(hours=SCHED_HOURS)
            logger.info("Using hours trigger. Interval: %s hours", SCHED_HOURS)

        next_run = datetime.now() if run_immediately else None

        # Add job with safety parameters
        self.job = self.scheduler.add_job(
            func=self._job_wrapper,
            trigger=trigger,
            id='auto_upload',
            replace_existing=True,
            next_run_time=next_run,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
            args=[]
        )
        logger.info('AutoUploader started for folder %s, next_run=%s', folder_id, str(next_run))
        logger.debug("Scheduled jobs: %s", self.scheduler.get_jobs())

    def stop(self):
        if self.job:
            try:
                self.scheduler.remove_job(self.job.id)
                logger.info("Removed job %s", self.job.id)
            except Exception:
                logger.exception("Error removing job")
            self.job = None
            logger.info('AutoUploader stopped')

    def _job_wrapper(self):
        """Wrapper to ensure Flask app context and exception visibility."""
        if not self.app:
            logger.error("AutoUploader has no app context bound; job aborting.")
            return

        # Use app context so utilities referencing current_app/config work correctly
        with self.app.app_context():
            try:
                self._job_upload_random()
            except Exception:
                logger.exception("Unhandled exception inside scheduled job")

    def _job_upload_random(self):
        logger.info('Auto job triggered — picking a random video from folder %s', self.folder_id)
        creds = load_credentials()
        if not creds:
            logger.warning('No credentials available for scheduled upload')
            return

        # Build API clients
        drive_service = build_drive_service(creds)
        youtube_service = build_youtube_service(creds)

        # Pick a random video from folder
        video_meta = pick_random_video_from_folder(drive_service, self.folder_id)
        if not video_meta:
            logger.warning('No video found in folder %s', self.folder_id)
            return

        file_id = video_meta['id']
        title = video_meta.get('name') or 'Short'
        try:
            # Fetch trending tags (returns list)
            tags = fetch_trending_hashtags(youtube_service, regionCode=self.region) or []
        except Exception:
            logger.exception("Failed to fetch trending hashtags; proceeding without them")
            tags = []

        description = f'Auto-upload from folder {self.folder_id}'

        try:
            logger.info('Downloading file %s', file_id)
            sp = download_drive_file_to_spooled(drive_service, file_id)
            # ensure seek to start in case spooled file not at 0
            try:
                sp.seek(0)
            except Exception:
                pass

            logger.info('Uploading file to YouTube: title="%s" tags=%s', title, tags[:10])
            video_id = upload_video_from_fileobj(youtube_service, sp, title, description, tags=tags)
            logger.info('Auto-upload succeeded: video id=%s', video_id)

        except Exception:
            logger.exception('Auto-upload failed for file_id=%s', file_id)
