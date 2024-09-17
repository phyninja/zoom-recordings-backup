import os
import requests
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pickle
from googleapiclient.http import MediaFileUpload
from dateutil.relativedelta import relativedelta
import json
import time

from tqdm import tqdm  # Import tqdm for progress bar

import requests
import datetime
import base64
from dateutil.relativedelta import relativedelta

from googleapiclient.discovery import build

import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
USER_ID = os.getenv('USER_ID')
REFRESH_TOKEN = os.getenv('REFRESH_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    config_file = "C:\\Users\\CTL 32\\OneDrive\\Documents\\Zoom Cloud Recording Sync App\\config.json"
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    if os.path.getsize(config_file) == 0:
        raise ValueError(f"Configuration file is empty: {config_file}")
    
    with open(config_file, 'r') as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON from file: {config_file}") from e
    return config

def check_zoom_rate_limits():
    url = 'https://api.zoom.us/v2/users/vivek@codingal.com/recordings'
    headers = {'Authorization': 'Bearer YOUR_ACCESS_TOKEN'}
    response = requests.get(url, headers=headers)
    
    # Print rate limit headers
    print(response.headers.get('X-RateLimit-Limit'))
    print(response.headers.get('X-RateLimit-Remaining'))
    print(response.headers.get('X-RateLimit-Reset'))

def check_drive_quota(service):
    about = service.about().get(fields='storageQuota').execute()
    print(about['storageQuota'])


# Google Drive API setup
def authenticate_google_drive(CREDENTIALS_FILE, SCOPES):
    """Authenticate and create the Google Drive API service."""
    creds = None
    
    # The file token.pickle stores the user's access and refresh tokens, and is created
    # automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    service = build('drive', 'v3', credentials=creds)
    return service

def download_recording(url, file_name, expected_size=None):
    max_retries = 3
    retry_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            start_time = time.time()  # Start time
            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size=0
            with open(file_name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total_size += len(chunk)
            end_time = time.time()  # End time

             # Check if the downloaded file matches the expected size
            if expected_size and total_size != expected_size:
                raise ValueError(f"Downloaded size {total_size} does not match expected size {expected_size}")
       
            # Calculate speed
            file_size = os.path.getsize(file_name)
            time_taken = end_time - start_time
            speed = file_size / time_taken  # bytes per second

            logging.info(f"Downloaded {file_name}, Size: {file_size} bytes, Time: {time_taken:.2f} seconds, Speed: {speed / (1024 * 1024):.2f} MB/s")
            print(f"Downloaded {file_name}, Size: {file_size} bytes, Time: {time_taken:.2f} seconds, Speed: {speed / (1024 * 1024):.2f} MB/s")
            return

        except requests.RequestException as e:
            print(f"Error downloading {url}: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to download {url} after {max_retries} attempts")

        except ValueError as ve:
            print(f"Download size mismatch: {ve}")
            os.remove(file_name)

def create_drive_folder(service, folder_name, parent_folder_id=None):
    """Create a folder in Google Drive and return the folder ID."""
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id] if parent_folder_id else []
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    print(f"Created folder '{folder_name}' with ID: {folder['id']}")
    return folder['id']

def create_folders_and_download(recordings_data, base_dir, service, root_folder_id, ACCESS_TOKEN=None):

    for recording in recordings_data:
        # Format the folder name as <topic>_<start_time> in YYYY-MM-DD HH:MM format
        # Format the start_time and replace invalid characters for folder names
        start_time = recording['start_time']
        formatted_start_time = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H-%M")
        folder_name = f"{recording['topic']} {formatted_start_time}"

        # Replace any other potentially invalid characters if necessary (e.g., for Windows)
        folder_name = folder_name.replace(':', '-').replace('/', '-').replace('\\', '-')

        # Create folder in Google Drive
        meeting_folder_id = create_drive_folder(service, folder_name, root_folder_id)

        # Create folder in local storage
        meeting_folder = os.path.join(base_dir, folder_name)
        os.makedirs(meeting_folder, exist_ok=True)
        
        for file in recording.get('recording_files', []):
            try:
                file_url = file['download_url'] + "?access_token=" + ACCESS_TOKEN
                file_extension = file['file_extension'].lower()
                
                # Use recording_type as the file name
                local_path = os.path.join(meeting_folder, f"{file['recording_type'].replace(' ', '_')}.{file_extension}")

                # Fetch the expected size from the metadata
                expected_size = file.get('file_size', None)
                
                # Download and upload each recording file
                download_recording(file_url, local_path, expected_size=expected_size)

                # Ensure the file has content before uploading
                if os.path.getsize(local_path) < 8:  # Example size threshold (1B)
                    raise ValueError(f"File {local_path} is too small to upload.")

                upload_to_drive(service, local_path, meeting_folder_id)
                
                # Remove the local file after successful upload
                os.remove(local_path)

                print(f"Folder and files for {recording['uuid']} created and downloaded successfully.")
            except Exception as e:
                print(f"Error processing meeting {recording['uuid']}: {str(e)}")


def upload_to_drive(service, file_path, folder_id):
    max_retries = 3
    retry_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            start_time = time.time()  # Start time
            file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
            }
            # Set up the MediaFileUpload with resumable=True
            media = MediaFileUpload(file_path, resumable=True)

            # Log the file size before upload
            file_size = os.path.getsize(file_path)
            print(f"Uploading {file_path}, size: {file_size} bytes")

            # Create the file with the option for resumable upload
            req = service.files().create(body=file_metadata, media_body=media, fields='id')

            # Create a progress bar
            progress_bar = tqdm(total=os.path.getsize(file_path), unit='B', unit_scale=True, unit_divisor=1024, desc=f"Uploading {os.path.basename(file_path)}")

            def progress_callback(req, response):
                if req.resumable_progress:
                    # Update progress bar
                    progress_bar.update(req.resumable_progress - progress_bar.n)
                if response:
                    # Complete the progress bar if upload is finished
                    progress_bar.update(file_size - progress_bar.n)

            # Upload the file in chunks
            response = None
            while response is None:
                status, response = req.next_chunk()
                if status:
                    progress_callback(status, response)

            end_time = time.time()  # End time

            # Close the progress bar
            progress_bar.close()

            # Calculate speed
            time_taken = end_time - start_time
            speed = file_size / time_taken  # bytes per second

            logging.info(f"Uploaded {file_path}, Size: {file_size} bytes, Time: {time_taken:.2f} seconds, Speed: {speed / (1024 * 1024):.2f} MB/s")
            print(f"Uploaded {file_path}, Size: {file_size} bytes, Time: {time_taken:.2f} seconds, Speed: {speed / (1024 * 1024):.2f} MB/s")
            return

        except Exception as e:
            print(f"Error uploading {file_path}: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to upload {file_path} after {max_retries} attempts")


def encode_credentials(client_id, client_secret):
    credentials = f"{client_id}:{client_secret}"
    return base64.b64encode(credentials.encode()).decode()


def refresh_access_token():
    token_url = "https://zoom.us/oauth/token"
    headers = {
        "Authorization": f"Basic {encode_credentials(CLIENT_ID, CLIENT_SECRET)}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    }
    response = requests.post(token_url, headers=headers, data=token_data)
    if response.status_code == 200:
        token_info = response.json()
        global ACCESS_TOKEN
        ACCESS_TOKEN = token_info['access_token']
        print("Access Token refreshed successfully")
        return ACCESS_TOKEN
    else:
        print(f"Error refreshing access token: {response.status_code} {response.text}")
        return None

def fetch_recordings(start_date, end_date):
    url = f"https://api.zoom.us/v2/users/{USER_ID}/recordings"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    # Format the dates in the required format (YYYY-MM-DD)
    params = {
        "from": f"{start_date}T00:00:00Z",
        "to": f"{end_date}T23:59:59Z",
        "page_size": 30  # Adjust page_size if needed
    }

    recordings = []
    while True:
        print(f"Request URL: {url}")
        print(f"Parameters: {params}")

        response = requests.get(url, headers=headers, params=params)
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")

        if response.status_code == 401:  # Invalid access token
            print("Access token invalid, refreshing...")
            new_token = refresh_access_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.get(url, headers=headers, params=params)
                print("Access Token refreshed successfully")
            else:
                print("Failed to refresh access token.")
                return recordings  # Exit with whatever data we have so far
        
        if response.status_code == 200:
            data = response.json()
            print(f"Data received for page:")
            print(f"From: {data['from']} To: {data['to']}")
            print(f"Total Records: {data['total_records']}")
            if data.get('meetings'):
                print(f"Sample Meeting: {data['meetings'][0]['topic']} | {data['meetings'][0]['start_time']}")
                recordings.extend(data['meetings'])  # Collect meetings data
            else:
                print("No meetings found in this time period.")
                break

            # Check if there are more pages
            next_page_token = data.get('next_page_token')
            if next_page_token:
                print("Next page token found, fetching next page...")
                params['next_page_token'] = next_page_token
            else:
                print("No more pages to fetch.")
                break

        else:
            print(f"Error fetching recordings: {response.status_code} {response.text}")
            break
        
    print("All recordings fetched successfully:")
    print(f"Total meetings fetched: {len(recordings)}")
    return recordings

def main():
    try:
        config = load_config()
        base_dir = config['base_dir']
        start_date = config['start_date']
        end_date = config['end_date']
        today = datetime.date.today()

        CREDENTIALS_FILE = config['credentials_file']
        # Scopes required by your application
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        service = authenticate_google_drive(CREDENTIALS_FILE, SCOPES)

        root_folder_id = config['upload_path']

        check_zoom_rate_limits()
        check_drive_quota(service)

        while True:
            recordings_data = fetch_recordings(start_date, end_date)
            if not recordings_data:
                break

            # Create folders and download files while preserving structure
            print("Starting folder creation and download process...")
            create_folders_and_download(recordings_data, base_dir, service, root_folder_id, ACCESS_TOKEN)
            print("Folder creation and download completed.")

            # Move to the next month
            start_date = end_date
            end_date = (datetime.strptime(end_date, "%Y-%m-%d") + relativedelta(months=1) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        print("All recordings processed and uploaded successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
    
if __name__ == "__main__":
    main()
