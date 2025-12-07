import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import SCHED_HOURS
from drive_utils import build_drive_service, pick_random_video_from_folder, download_drive_file_to_spooled
from youtube_utils import build_youtube_service, upload_video_from_fileobj
from tags_utils import fetch_trending_hashtags
from auth_utils import load_credentials

logger = logging.getLogger('scheduler_utils')


class AutoUploader:
    def __init__(self, app=None):
        self.app = app
        self.scheduler = BackgroundScheduler()
        self.job = None
        self.folder_id = None
        self.region = None

    def init_app(self, app):
        self.app = app
        self.scheduler.start()

    def start(self, folder_id, region='US'):
        self.folder_id = folder_id
        self.region = region
        if self.job:
            self.stop()
        # Add job with interval trigger
        self.job = self.scheduler.add_job(self._job_upload_random,
                                          trigger=IntervalTrigger(hours=SCHED_HOURS),
                                          id='auto_upload',
                                          replace_existing=True,
                                          next_run_time=None)  # next_run_time None => schedule first at next interval
        logger.info('AutoUploader started for folder %s every %d hours', folder_id, SCHED_HOURS)

    def stop(self):
        if self.job:
            try:
                self.scheduler.remove_job(self.job.id)
            except Exception:
                pass
            self.job = None
            logger.info('AutoUploader stopped')

    def _job_upload_random(self):
        logger.info('Auto job triggered — picking a random video from folder %s', self.folder_id)
        creds = load_credentials()
        if not creds:
            logger.warning('No credentials available for scheduled upload')
            return
        drive_service = build_drive_service(creds)
        youtube_service = build_youtube_service(creds)

        video_meta = pick_random_video_from_folder(drive_service, self.folder_id)
        if not video_meta:
            logger.warning('No video found in folder %s', self.folder_id)
            return
        file_id = video_meta['id']
        title = video_meta.get('name') or 'Short'
        tags = fetch_trending_hashtags(youtube_service, regionCode=self.region)
        description = f'Auto-upload from folder {self.folder_id}'
        try:
            logger.info('Downloading file %s', file_id)
            sp = download_drive_file_to_spooled(drive_service, file_id)
            video_id = upload_video_from_fileobj(youtube_service, sp, title, description, tags=tags)
            logger.info('Auto-upload succeeded: video id=%s', video_id)
        except Exception as e:
            logger.exception('Auto-upload failed: %s', e)
