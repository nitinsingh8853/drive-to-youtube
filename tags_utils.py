import logging
import re
from collections import Counter
from googleapiclient.discovery import build
from pytrends.request import TrendReq
from config import TREND_VIDEO_LIMIT, DEFAULT_REGION, MAX_HASHTAGS

logger = logging.getLogger('tags_utils')

HASHTAG_RE = re.compile(r'#(\w+)')


def extract_hashtags_from_text(text):
    return HASHTAG_RE.findall(text or '')


def fetch_trending_hashtags_via_youtube(youtube_service, regionCode=DEFAULT_REGION, max_videos=TREND_VIDEO_LIMIT):
    """Use YouTube mostPopular videos to derive popular hashtags/tags."""
    tags_counter = Counter()
    try:
        # youtube_service.videos().list supports maxResults up to 50. We request up to max_videos (≤50).
        res = youtube_service.videos().list(part='snippet', chart='mostPopular', regionCode=regionCode, maxResults=min(max_videos, 50)).execute()
        for item in res.get('items', []):
            snippet = item.get('snippet', {})
            # explicit tags
            for t in snippet.get('tags', []) or []:
                if t.startswith('#'):
                    tags_counter[t.lower()] += 2
                else:
                    tags_counter[('#' + t.lower())] += 1
            # hashtags in title/description
            text = (snippet.get('title', '') + '\n' + snippet.get('description', ''))
            for h in extract_hashtags_from_text(text):
                tags_counter[('#' + h.lower())] += 3
    except Exception as e:
        logger.exception('YouTube trending fetch failed: %s', e)

    tags = [t for t, _ in tags_counter.most_common(MAX_HASHTAGS)]
    return tags


def fetch_trending_hashtags_via_pytrends(geo='US', top_k=MAX_HASHTAGS):
    """Fallback using Google Trends (pytrends) trending searches."""
    try:
        pt = TrendReq()
        # Use trending_searches - returns a pandas Series-like structure
        df = pt.trending_searches(pn='united_states') if geo.upper() in ('US', 'UNITED_STATES') else pt.trending_searches()
        items = []
        # robust slicing depending on return type
        try:
            items = list(df.head(top_k).values)
        except Exception:
            try:
                items = list(df[:top_k])
            except Exception:
                items = []
        tags = []
        for term in items:
            term = str(term).strip()
            if not term:
                continue
            # sanitize to alphanumeric only
            clean = ''.join(ch for ch in term if ch.isalnum())
            if not clean:
                continue
            tags.append('#' + clean.lower())
        return tags[:top_k]
    except Exception as e:
        logger.exception('pytrends fetch failed: %s', e)
        return []


def fetch_trending_hashtags(youtube_service, regionCode=DEFAULT_REGION):
    # prefer YouTube-based extraction
    tags = fetch_trending_hashtags_via_youtube(youtube_service, regionCode=regionCode)
    if tags:
        return tags
    return fetch_trending_hashtags_via_pytrends(geo=regionCode)
