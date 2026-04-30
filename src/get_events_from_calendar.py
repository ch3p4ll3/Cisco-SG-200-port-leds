import datetime
import os.path
from pathlib import Path
from logging import getLogger

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
logger = getLogger(__file__)


def get_events(email_to_seach: str, base_path: Path):
  """Shows basic usage of the Google Calendar API.
  prints the start and name of the next 10 events on the user's calendar.
  """
  token_file = base_path.parent / "data/token.json"
  credentials_file = base_path.parent / "data/credentials.json"

  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists(token_file):
    print("ok")
    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          credentials_file, SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open(token_file, "w") as token:
      token.write(creds.to_json())

  try:
    service = build("calendar", "v3", credentials=creds)

    # Call the Calendar API
    now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    logger.debug("Getting the upcoming 10 events")
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
      logger.debug("No upcoming events found.")
      return

    # logger.debugs the start and name of the next 10 events
    for event in events:
      attendes = event.get('attendees', [])

      if email_to_seach in [i.get('email', '') for i in attendes]:
        yield event

  except HttpError as error:
    logger.error(f"An error occurred: {error}", exc_info=True)
