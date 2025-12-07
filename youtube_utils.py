import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger('youtube_utils')


def build_youtube_service(creds):
    return build('youtube', 'v3', credentials=creds, cache_discovery=False)


def upload_video_from_fileobj(youtube_service, fileobj, title, description, tags=None, privacy='public', chunk_size=256 * 1024):
    """Upload a video using a file-like object. Returns YouTube video id."""
    if hasattr(fileobj, 'seek'):
        try:
            fileobj.seek(0)
        except Exception:
            # ignore if not seekable
            pass

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or []
        },
        'status': {
            'privacyStatus': privacy
        }
    }
    media = MediaIoBaseUpload(fileobj, mimetype='video/*', chunksize=chunk_size, resumable=True)
    request = youtube_service.videos().insert(part=','.join(['snippet', 'status']), body=body, media_body=media)
    logger.info('Starting resumable upload to YouTube (title=%s)', title)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info('Upload progress: %d%%', int(status.progress() * 100))
    video_id = response.get('id')
    logger.info('Upload finished: video id=%s', video_id)
    return video_id


def set_thumbnail(youtube_service, video_id, thumb_fileobj=None):
    if thumb_fileobj is None:
        return None
    try:
        if hasattr(thumb_fileobj, 'seek'):
            thumb_fileobj.seek(0)
    except Exception:
        pass
    media = MediaIoBaseUpload(thumb_fileobj, mimetype='image/jpeg', resumable=False)
    res = youtube_service.thumbnails().set(videoId=video_id, media_body=media).execute()
    logger.info('Thumbnail set response: %s', res)
    return res
