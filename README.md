# Drive → YouTube Shorts (Modular Flask App)

This app lets you upload videos from Google Drive to YouTube (Shorts) either manually or automatically on a schedule.

Features:
- Manual: paste a Drive file ID and upload it as a YouTube video.
- Folder: provide a Drive folder ID and the app can pick a random video and upload.
- Automatic: run scheduled job every 3 hours to pick a random video from a folder and upload with trending hashtags.
- No user-local videos: files are downloaded from Drive into memory/spooled temporary files and uploaded to YouTube.

## Setup

1. Create a Google Cloud project. Enable:
   - Google Drive API
   - YouTube Data API v3

2. Create OAuth 2.0 Client Credentials (Application type: **Web application**).
   - Add an authorized redirect URI: `http://localhost:5000/oauth2callback`
   - Download the JSON and save as `credentials.json` in the project root.

3. Install dependencies:
```bash
pip install -r requirements.txt
