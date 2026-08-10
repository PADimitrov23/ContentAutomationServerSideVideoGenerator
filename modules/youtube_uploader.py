import os
import pickle
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.exceptions import RefreshError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = os.path.join(os.getcwd(), "assets", "youtube_token.pickle")
CLIENT_SECRETS_FILE = os.path.join(os.getcwd(), "assets", "client_secret.json")

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
                print("Missing client_secret.json. Set up OAuth first.")
                print("Run: python setup_youtube.py")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            auth_url, _ = flow.authorization_url(prompt="consent")
            print("=" * 60)
            print("OPEN THIS URL in your browser (Windows machine):")
            print(auth_url)
            print()
            print("IMPORTANT: Sign in with the Google account that owns the YouTube channel")
            print("=" * 60)
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
            print("Removed expired token file. Re-run `python setup_youtube.py` to re-authorize.")
    except Exception:
        pass

def setup_oauth():
    get_authenticated_service()
    print("YouTube OAuth setup complete. Token saved.")

def upload_video(video_path, title="YouTube Short", description="", privacy_status="public"):
    youtube = get_authenticated_service()
    if not youtube:
        raise TokenExpiredError("No valid YouTube credentials available.")
    body = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": privacy_status}
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    try:
        response = request.execute()
        print(f"Uploaded: https://youtu.be/{response['id']}")
        return response["id"]
    except Exception as e:
        err_str = str(e)
        if "invalid_grant" in err_str or "invalid_scope" in err_str:
            _delete_bad_token()
            raise TokenExpiredError("YouTube token expired or revoked. Run `python setup_youtube.py` to re-authorize.")
        raise

if __name__ == "__main__":
    setup_oauth()
