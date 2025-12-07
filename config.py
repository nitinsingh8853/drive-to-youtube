import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'credentials.json')  # place your downloaded OAuth client JSON here
TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')                 # created after first authorize
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/youtube.upload',
]

# Scheduler interval (hours) for automatic upload
SCHED_HOURS = 1
SCHED_TEST_MODE = False

# Region for fetching mostPopular videos (for trending tags)
DEFAULT_REGION = 'US'

# Limit how many videos to inspect for trending tags
TREND_VIDEO_LIMIT = 25

# Max number of hashtags to attach
MAX_HASHTAGS = 10

# Spooled temp max in-memory size (bytes) before spilling to disk
SPOOLED_MAX_MEM = 20 * 1024 * 1024  # 20 MB (adjust for larger files)
