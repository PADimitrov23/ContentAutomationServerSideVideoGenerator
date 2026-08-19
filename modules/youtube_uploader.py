import os
import re
import pickle
import logging
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.exceptions import RefreshError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = os.path.join(os.getcwd(), "assets", "youtube_token.pickle")
CLIENT_SECRETS_FILE = os.path.join(os.getcwd(), "assets", "client_secret.json")

CORE_HASHTAGS = [
    "#DavidGoggins",
    "#Motivation",
    "#StayHard",
    "#NoExcuses",
    "#Mindset",
    "#Discipline",
    "#MentalToughness",
    "#Grind",
    "#NeverQuit",
    "#HardWork",
]

TOPIC_KEYWORDS = {
    "pain": ["#Pain", "#EmbraceTheSuck", "#Suffering"],
    "quit": ["#NeverQuit", "#DontQuit", "#KeepGoing"],
    "lazy": ["#StopBeingLazy", "#Discipline", "#WakeUp"],
    "tired": ["#ImNotTired", "#40PercentRule", "#PushThrough"],
    "fear": ["#FaceYourFears", "#Courage", "#Bravery"],
    "weak": ["#GetStronger", "#MentalToughness", "#Resilience"],
    "excuse": ["#NoExcuses", "#StopMakingExcuses", "#Accountability"],
    "hard": ["#HardMode", "#StayHard", "#EmbraceTheSuck"],
    "fail": ["#Failure", "#LearnFromFailure", "#GetBackUp"],
    "goal": ["#Goals", "#DreamBig", "#AchieveMore"],
    "early": ["#WakeUpEarly", "#5AmClub", "#MorningRoutine"],
    "gym": ["#Gym", "#Workout", "#FitnessMotivation"],
    "run": ["#Running", "#Ultrarunning", "#Endurance"],
    "seal": ["#NavySEAL", "#MilitaryMotivation", "#BUDS"],
    "mind": ["#Mindset", "#MentalStrength", "#Psychology"],
    "life": ["#LifeLessons", "#LifeMotivation", "#RealTalk"],
    "money": ["#MoneyMindset", "#Wealth", "#FinancialFreedom"],
    "success": ["#Success", "#Winner", "#Champion"],
    "change": ["#ChangeYourLife", "#Transformation", "#Growth"],
    "story": ["#StoryTime", "#RealStory", "#MotivationalStory"],
}


def generate_hashtags(script_text):
    text_lower = script_text.lower()
    hashtags = list(CORE_HASHTAGS)

    for keyword, tags in TOPIC_KEYWORDS.items():
        if keyword in text_lower:
            for tag in tags:
                if tag not in hashtags:
                    hashtags.append(tag)

    return hashtags[:15]


def generate_description(script_text, hashtags):
    tag_line = " ".join(hashtags[:10])
    description = f"{tag_line}\n\nStay Hard. No excuses."
    return description


def generate_tags(script_text):
    base_tags = [
        "david goggins",
        "motivation",
        "motivational video",
        "stay hard",
        "no excuses",
        "mindset",
        "discipline",
        "mental toughness",
        "self improvement",
        "inspiration",
        "youtube shorts",
        "shorts",
    ]

    text_lower = script_text.lower()
    topic_tags = []
    for keyword in TOPIC_KEYWORDS:
        if keyword in text_lower:
            topic_tags.append(keyword)

    extra = [
        "goggins motivation",
        "navy seal motivation",
        "hard truth",
        "real talk",
        "grind mindset",
        "never quit",
        "push through pain",
    ]

    all_tags = base_tags + topic_tags + extra
    seen = set()
    unique = []
    for t in all_tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:30]


class TokenExpiredError(Exception):
    pass


def get_token_expiry():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "rb") as f:
            credentials = pickle.load(f)
        return credentials.expiry
    except Exception:
        return None


def is_token_valid():
    expiry = get_token_expiry()
    if expiry is None:
        return False
    return expiry > datetime.now(expiry.tzinfo) + timedelta(hours=1)


def get_authenticated_service():
    credentials = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "rb") as f:
                credentials = pickle.load(f)
        except Exception:
            credentials = None
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                _delete_bad_token()
                raise TokenExpiredError(
                    "YouTube token is no longer valid. Run `python setup_youtube.py` to re-authorize."
                )
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                logger.error("Missing client_secret.json. Run: python setup_youtube.py")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            auth_url, _ = flow.authorization_url(prompt="consent")
            print(f"\nOPEN THIS URL IN YOUR BROWSER:\n{auth_url}\n")
            code = input("Enter the authorization code: ").strip()
            flow.fetch_token(code=code)
            credentials = flow.credentials
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(credentials, f)
    return build("youtube", "v3", credentials=credentials)


def _delete_bad_token():
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            logger.warning("Removed expired token. Re-run: python setup_youtube.py")
    except Exception:
        pass


def setup_oauth():
    get_authenticated_service()
    logger.info("YouTube OAuth setup complete.")


def upload_video(video_path, title="YouTube Short", description="", tags=None, privacy_status="public"):
    youtube = get_authenticated_service()
    if not youtube:
        raise TokenExpiredError("No valid YouTube credentials available.")

    snippet = {
        "title": title,
        "description": description,
    }
    if tags:
        snippet["tags"] = tags

    body = {
        "snippet": snippet,
        "status": {"privacyStatus": privacy_status},
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    try:
        response = request.execute()
        url = f"https://youtu.be/{response['id']}"
        logger.info(f"Uploaded: {url}")
        return response["id"]
    except Exception as e:
        err_str = str(e)
        if "invalid_grant" in err_str or "invalid_scope" in err_str:
            _delete_bad_token()
            raise TokenExpiredError("YouTube token expired. Re-run: python setup_youtube.py")
        raise


if __name__ == "__main__":
    setup_oauth()
