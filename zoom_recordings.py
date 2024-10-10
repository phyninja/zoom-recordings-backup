import os
import requests
import pickle
from dateutil.relativedelta import relativedelta
import json
import time
from tqdm import tqdm  # Import tqdm for progress bar
import datetime
import base64
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

if not all([ACCESS_TOKEN, USER_ID, REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET]):
    raise ValueError("Missing one or more environment variables.")

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    config_file = "C:\\Users\\CTL-118\\Documents\\zoom-recordings-backup-main\\config.json"
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

def download_recording(url, file_name, expected_size=None):
    max_retries = 3
    retry_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            start_time = time.time()  # Start time
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_size=0

            with open(file_name, 'wb') as f, tqdm(total=expected_size, unit='B', unit_scale=True, desc=file_name) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total_size += len(chunk)
                    pbar.update(len(chunk))

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

def create_folders_and_download(recordings_data, base_dir, ACCESS_TOKEN=None):

    for recording in recordings_data:
        # Format the folder name as <topic>_<start_time> in YYYY-MM-DD HH:MM format
        # Format the start_time and replace invalid characters for folder names
        start_time = recording['start_time']
        formatted_start_time = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d at %H-%M")
        folder_name = f"{recording['topic']} {formatted_start_time}"

        # Replace any other potentially invalid characters if necessary (e.g., for Windows)
        folder_name = folder_name.replace(':', '-').replace('/', '-').replace('\\', '-').replace('<','-').replace('>','-').replace('|','-').replace('?','Q').replace('*','asterisk').strip()

        # Create folder in local Google Drive folder
        meeting_folder = os.path.join(base_dir, folder_name)
        os.makedirs(meeting_folder, exist_ok=True)
        
        for file in recording.get('recording_files', []):
            try:
                file_url = file['download_url'] + "?access_token=" + ACCESS_TOKEN
                file_extension = file['file_extension'].lower()
                
                # Convert the strings to datetime objects
                start_time = datetime.datetime.strptime(file['recording_start'], "%Y-%m-%dT%H:%M:%SZ")
                end_time = datetime.datetime.strptime(file['recording_end'], "%Y-%m-%dT%H:%M:%SZ")

                # Calculate the duration
                recording_length = end_time - start_time
                duration_in_minutes = int(recording_length.total_seconds() // 60) #Convert to minutes

                # Construct the local path using os.path.join, with safe file naming and proper formatting
                local_path = os.path.join(meeting_folder, f"{file['recording_type'].replace(' ', '_')}_duration_{duration_in_minutes}_minutes.{file_extension}")

                # Fetch the expected size from the metadata
                expected_size = file.get('file_size', None)
                
                # # Download and upload each recording file
                download_recording(file_url, local_path, expected_size=expected_size)

                print(f"Folder and files for {recording['uuid']} created and downloaded successfully.")
            except Exception as e:
                print(f"Error processing meeting {recording['uuid']}: {str(e)}")
                logging.error(f"An error occurred: {e}", exc_info=True)


def encode_credentials(client_id, client_secret):
    credentials = f"{client_id}:{client_secret}"
    return base64.b64encode(credentials.encode()).decode('utf-8')


def refresh_access_token():
    global ACCESS_TOKEN, REFRESH_TOKEN
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
        print("Access Token refreshed successfully")
        ACCESS_TOKEN = token_info['access_token']
        REFRESH_TOKEN = token_info['refresh_token']
    else:
        print(f"Error refreshing access token: {response.status_code} {response.text}")

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
        #print(f"Request URL: {url}")
        #print(f"Parameters: {params}")

        response = requests.get(url, headers=headers, params=params)
        #print(f"Response Status Code: {response.status_code}")
        #print(f"Response Content: {response.text}")

        if response.status_code == 401:  # Invalid access token
            print("Access token invalid, refreshing...")

            old_token = ACCESS_TOKEN

            refresh_access_token()

            if ACCESS_TOKEN != old_token:
                headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
                response = requests.get(url, headers=headers, params=params)
                print("Access Token refreshed successfully")
            else:
                print("Failed to refresh access token.")
                return recordings  # Exit with whatever data we have so far
        
        if response.status_code == 200:
            data = response.json()
            #print(f"Data received for page:")
            print(f"From: {data['from']} To: {data['to']}")
            print(f"Total Records: {data['total_records']}")
            if data.get('meetings'):
                #print(f"Sample Meeting: {data['meetings'][0]['topic']} | {data['meetings'][0]['start_time']}")
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
        base_dir = os.path.join(config['base_dir'], USER_ID)
        start_date = config['start_date']
        config_end_date = config['end_date']
        today = datetime.date.today()

        # Initialize access token timer and refresh frequency
        access_token_refresh_frequency = config.get('access_token_refresh_frequency', 3500)  # default to 1 hour if not set
        access_token_elapsed_time = time.time()

        # Initial access token refresh
        refresh_access_token()

        check_zoom_rate_limits()

        while True:
            # Refresh access token if time exceeds the refresh frequency
            if time.time() - access_token_elapsed_time >= access_token_refresh_frequency:
                refresh_access_token()
                access_token_elapsed_time = time.time()

            # Calculate end_date as the earlier of 'start_date + 1 month' and 'config_end_date'
            calculated_end_date = (datetime.datetime.strptime(start_date, "%Y-%m-%d") + relativedelta(months=1) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = min(calculated_end_date, config_end_date)

            # Print statement for clarity during testing
            print(f"Fetching recordings from {start_date} to {end_date}")

            recordings_data = fetch_recordings(start_date, end_date)
            
            # No recordings found for this period but continue to the next month
            if not recordings_data:
                print(f"No recordings found from {start_date} to {end_date}, moving to the next month.")
                start_date = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                if start_date > config_end_date:  # Break if we're past the config's end_date
                    break
                continue

            # Create folders and download files while preserving structure
            print("Starting folder creation and download process...")
            create_folders_and_download(recordings_data, base_dir, ACCESS_TOKEN)
            print("Folder creation and download completed.")

            # Move to the next month
            start_date = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            # Break if we've passed the final end_date from the config
            if start_date > config_end_date:
                break
        
        print("All recordings processed and uploaded successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logging.error(f"An error occurred: {e}", exc_info=True)
    
if __name__ == "__main__":
    main()
