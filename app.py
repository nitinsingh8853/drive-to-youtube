import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from google_auth_oauthlib.flow import Flow
from auth_utils import load_credentials, save_credentials, revoke_credentials
from config import CLIENT_SECRETS_FILE, SCOPES
from drive_utils import build_drive_service, download_drive_file_to_spooled, pick_random_video_from_folder
from youtube_utils import build_youtube_service, upload_video_from_fileobj, set_thumbnail
from tags_utils import fetch_trending_hashtags
from scheduler_utils import AutoUploader

# For local development only — allow http redirect
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('app')


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET', 'change-me')

    # Scheduler
    app.auto_uploader = AutoUploader()
    app.auto_uploader.init_app(app)

    @app.route('/')
    def index():
        creds = load_credentials()
        return render_template('index.html', authorized=bool(creds))

    @app.route('/authorize')
    def authorize():
        if not os.path.exists(CLIENT_SECRETS_FILE):
            return 'Place credentials.json in the application folder.'
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=url_for('oauth2callback', _external=True))
        auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
        session['state'] = state
        return redirect(auth_url)

    @app.route('/oauth2callback')
    def oauth2callback():
        state = session.get('state')
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=url_for('oauth2callback', _external=True))
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        save_credentials(creds)
        flash('Authorization complete')
        return redirect(url_for('index'))

    @app.route('/revoke')
    def revoke():
        revoke_credentials()
        flash('Credentials cleared')
        return redirect(url_for('index'))

    # Manual upload route
    @app.route('/manual', methods=['GET', 'POST'])
    def manual():
        creds = load_credentials()
        if not creds:
            flash('Authorize first')
            return redirect(url_for('index'))
        if request.method == 'GET':
            return render_template('manual.html')
        # POST
        drive_file_id = (request.form.get('drive_file_id') or '').strip()
        if not drive_file_id:
            flash('Provide Drive file ID')
            return redirect(url_for('manual'))
        title = request.form.get('title') or 'Short'
        description = request.form.get('description') or ''
        tags_raw = request.form.get('tags') or ''
        tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
        thumb_drive_id = request.form.get('thumb_drive_id')

        try:
            drive_service = build_drive_service(creds)
            youtube_service = build_youtube_service(creds)
            sp = download_drive_file_to_spooled(drive_service, drive_file_id)
            # if tags empty, fetch trending tags
            if not tags:
                tags = fetch_trending_hashtags(youtube_service)
            video_id = upload_video_from_fileobj(youtube_service, sp, title, description, tags=tags)
            # thumbnail
            if thumb_drive_id:
                thumb_sp = download_drive_file_to_spooled(drive_service, thumb_drive_id, max_mem=1 * 1024 * 1024)
                set_thumbnail(youtube_service, video_id, thumb_fileobj=thumb_sp)
            return render_template('result.html', message=f'Uploaded video id: {video_id}')
        except Exception as e:
            logger.exception('Manual upload failed')
            return render_template('result.html', message=f'Error: {e}')

    # Folder single-upload (manual trigger)
    @app.route('/folder', methods=['GET', 'POST'])
    def folder():
        creds = load_credentials()
        if not creds:
            flash('Authorize first')
            return redirect(url_for('index'))
        if request.method == 'GET':
            return render_template('folder.html')
        folder_id = (request.form.get('folder_id') or '').strip()
        region = (request.form.get('region') or '').strip() or None
        if not folder_id:
            flash('Provide folder id')
            return redirect(url_for('folder'))

        try:
            drive_service = build_drive_service(creds)
            youtube_service = build_youtube_service(creds)
            video_meta = pick_random_video_from_folder(drive_service, folder_id)
            if not video_meta:
                return render_template('result.html', message='No video found in folder')
            sp = download_drive_file_to_spooled(drive_service, video_meta['id'])
            tags = fetch_trending_hashtags(youtube_service, regionCode=region) if region else fetch_trending_hashtags(youtube_service)
            title = video_meta.get('name') or 'Short'
            video_id = upload_video_from_fileobj(youtube_service, sp, title, f'Auto-pick from folder {folder_id}', tags=tags)
            return render_template('result.html', message=f'Uploaded video id: {video_id} (picked: {video_meta.get("name")})')
        except Exception as e:
            logger.exception('Folder manual upload failed')
            return render_template('result.html', message=f'Error: {e}')

    # Scheduler control
    @app.route('/scheduler/start', methods=['POST'])
    def sched_start():
        creds = load_credentials()
        if not creds:
            flash('Authorize first')
            return redirect(url_for('index'))
        folder_id = (request.form.get('folder_id') or '').strip()
        region = (request.form.get('region') or 'US').strip()
        if not folder_id:
            flash('Provide folder id')
            return redirect(url_for('index'))
        app.auto_uploader.start(folder_id, region=region)
        flash('Scheduler started')
        return redirect(url_for('index'))

    @app.route('/scheduler/stop')
    def sched_stop():
        app.auto_uploader.stop()
        flash('Scheduler stopped')
        return redirect(url_for('index'))

    return app


if __name__ == '__main__':
    app = create_app()
    # debug True is convenient for development, but disable in production!
    app.run('0.0.0.0', port=5000, debug=True)
