"""Upload a clip to YouTube as a Short (Data API v3)."""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from ..config import env

TOKEN_URI = "https://oauth2.googleapis.com/token"


def _service():
    creds = Credentials(
        token=None,
        refresh_token=env("YOUTUBE_REFRESH_TOKEN"),
        client_id=env("YOUTUBE_CLIENT_ID"),
        client_secret=env("YOUTUBE_CLIENT_SECRET"),
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def post(clip_path, title, description, hashtags):
    yt = _service()
    # #Shorts in the title/description is what flags it as a Short.
    tags = [h.lstrip("#") for h in hashtags]
    body = {
        "snippet": {
            "title": (title[:95] + " #Shorts"),
            "description": description + "\n\n#Shorts",
            "tags": tags[:15],
            "categoryId": "24",  # Entertainment
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(clip_path), mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = req.execute()
    vid = resp["id"]
    print(f"[youtube] posted https://youtube.com/shorts/{vid}")
    return vid
