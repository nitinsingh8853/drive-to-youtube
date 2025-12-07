import io
import random
import logging
import tempfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from config import SPOOLED_MAX_MEM

logger = logging.getLogger('drive_utils')


def build_drive_service(creds):
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def list_videos_in_folder(drive_service, folder_id, page_size=100):
    """Return list of file dicts for files in folder_id (best-effort video filtering)."""
    q = f"'{folder_id}' in parents and trashed=false"
    fields = 'nextPageToken, files(id, name, mimeType)'
    files = []
    page_token = None
    while True:
        res = drive_service.files().list(q=q, spaces='drive', fields=fields, pageToken=page_token, pageSize=page_size).execute()
        files.extend(res.get('files', []))
        page_token = res.get('nextPageToken')
        if not page_token:
            break
    # Filter likely videos (mimeType startswith video OR filename extension)
    video_files = []
    for f in files:
        m = f.get('mimeType', '')
        name = f.get('name', '').lower()
        if m.startswith('video') or name.endswith(('.mp4', '.mov', '.webm', '.mkv', '.avi', '.flv', '.mpeg')):
            video_files.append(f)
    return video_files


def pick_random_video_from_folder(drive_service, folder_id):
    vids = list_videos_in_folder(drive_service, folder_id)
    if not vids:
        return None
    return random.choice(vids)


def download_drive_file_to_spooled(drive_service, file_id, max_mem=SPOOLED_MAX_MEM):
    """Download Drive file into a SpooledTemporaryFile and return it (seeked to start)."""
    sp = tempfile.SpooledTemporaryFile(max_size=max_mem)
    request = drive_service.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(sp, request)
    done = False
    logger.info('Starting download of Drive file %s to spooled file', file_id)
    while not done:
        status, done = downloader.next_chunk()
        if status:
            logger.info('Download progress: %d%%', int(status.progress() * 100))
    sp.seek(0)
    logger.info('Download complete')
    return sp
