import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = os.path.join(os.getcwd(), "assets", "youtube_token.pickle")
CLIENT_SECRETS_FILE = os.path.join(os.getcwd(), "assets", "client_secret.json")

def get_authenticated_service():
    credentials = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            credentials = pickle.load(f)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
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

def setup_oauth():
    get_authenticated_service()
    print("YouTube OAuth setup complete. Token saved.")

def upload_video(video_path, title="YouTube Short", description="", privacy_status="public"):
    youtube = get_authenticated_service()
    if not youtube:
        return None
    body = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": privacy_status}
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"Uploaded: https://youtu.be/{response['id']}")
    return response["id"]

if __name__ == "__main__":
    setup_oauth()
