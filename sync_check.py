# sync_check.py

import os
from zoom_recordings import fetch_recordings, load_config, encode_credentials, refresh_access_token  # Import the fetch_recordings function from zoom_fetch
import re
import datetime
import time
from dateutil.relativedelta import relativedelta
import json
from fuzzywuzzy import fuzz
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

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def normalize_string(input_str):
    # Remove all non-alphabetical characters
    return re.sub(r'[^a-zA-Z0-9]', '', input_str).lower()

# Fetch Zoom Recording Metadata
def fetch_zoom_recording_metadata(start_date, end_date):
    recordings_data = fetch_recordings(start_date, end_date)
    zoom_recordings = {}
    for recording in recordings_data:
        start_time = recording['start_time']
        formatted_start_time = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d at %H-%M")
        normalized_folder_name = normalize_string(f"{recording['topic']} {formatted_start_time}")
        zoom_recordings[normalized_folder_name] = {
            'id' : recording['id'],
            'files': [(file['file_type'], file['file_size']) for file in recording['recording_files']]
        }
    return zoom_recordings

# Scan Local Folder Metadata
def scan_local_folders(base_dir):
    local_recordings = {}
    for root, dirs, files in os.walk(base_dir):
        normalized_folder_name = normalize_string(os.path.basename(root))
        local_recordings[normalized_folder_name] = {
            'files': [(os.path.splitext(f)[1][1:], os.path.getsize(os.path.join(root, f))) for f in files]
        }
    return local_recordings

def find_closest_match(folder_name, local_recordings):
    highest_ratio = 0
    best_match = None

    # Iterate over all local recordings
    for local_folder in local_recordings:
        # Calculate the similarity ratio between folder_name and each local_folder
        ratio = fuzz.ratio(folder_name, local_folder)

        # Keep track of the best match with the highest ratio
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = local_folder

    # If the best match has a ratio of 99% or more, return it
    if highest_ratio >= 99:
        return best_match
    else:
        return None

# Verify Sync Quality
def verify_sync(zoom_recordings, local_recordings, margin=0.01):
    missing_folders = []
    mismatched_files = []
    
    try:
        for folder_name, zoom_files in zoom_recordings.items():
            best_match = find_closest_match(folder_name, local_recordings)

            if not best_match:
                print(f"Folder {folder_name} not found in Local recordings")
                missing_folders.append(folder_name)
            else:
                local_files = local_recordings[best_match]['files']

                # Convert local_files to a dictionary where each file type (e.g., mp4, m4a) has a list of files
                local_files_dict = {}
                for file_type, file_size in local_files:
                    file_type = file_type.lower()
                    if file_type not in local_files_dict:
                        local_files_dict[file_type] = []
                    local_files_dict[file_type].append({'size': file_size})

                # Iterate over the zoom_files
                for zoom_file in zoom_files['files']:
                    try:
                        zoom_file_type = zoom_file[0].lower()  # Extracting the file type from the tuple
                        zoom_file_size = zoom_file[1]   # Extracting the file size from the tuple

                        if zoom_file_type in ['mp4', 'm4a']: #only care about verifying the backup of MP4 and M4A files
                            if zoom_file_type in local_files_dict:  # Ensure there are local files of the same type to compare with
                                local_files_of_type = local_files_dict[zoom_file_type]

                                # Try to find a matching local file by size
                                match_found = False
                                for local_file in local_files_of_type:
                                    local_file_size = local_file['size']

                                    # Calculate percentage difference
                                    size_difference = abs(zoom_file_size - local_file_size)
                                    percentage_difference = size_difference / zoom_file_size

                                    if percentage_difference <= margin:
                                        match_found = True
                                        local_files_of_type.remove(local_file)  # Remove matched file to prevent reuse
                                        break  # Exit the loop once a match is found
                                
                                if not match_found:
                                    mismatched_files.append(f"{best_match} {zoom_file_type} size mismatch: Zoom size {zoom_file_size}, No matching local file")
                            else:
                                mismatched_files.append(f"{zoom_file_type} not found in local folder {best_match}")
                        else:
                            continue # Skip non-MP4 and M4A files

                    except Exception as e:
                        print(f"An error occurred while iterating over zoom_files in the verify_sync function: {e}")

        return missing_folders, mismatched_files

    except Exception as e:
        print(f"An error occurred in the verify_sync function: {e}")

# Main Sync Check Logic
def main_sync_check():
    try:
        config = load_config()
        base_dir = config['base_dir']
        start_date = config['start_date']
        config_end_date = config['end_date']
        today = datetime.date.today()

        # Initialize access token timer and refresh frequency
        access_token_refresh_frequency = config.get('access_token_refresh_frequency', 3500)  # default to 1 hour if not set
        access_token_elapsed_time = time.time()

        # Initial access token refresh
        refresh_access_token()

        zoom_recordings = {}

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

            piecemal_zoom_recordings = fetch_zoom_recording_metadata(start_date, end_date)

            # No recordings found for this period but continue to the next month
            if not piecemal_zoom_recordings:
                print(f"No recordings found from {start_date} to {end_date}, moving to the next month.")
                start_date = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                if start_date > config_end_date:  # Break if we're past the config's end_date
                    break
                continue

            zoom_recordings.update(piecemal_zoom_recordings)

            # Move to the next month
            start_date = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            # Break if we've passed the final end_date from the config
            if start_date > config_end_date:
                break
        
        local_recordings = scan_local_folders(base_dir)
        
        missing_folders, mismatched_files = verify_sync(zoom_recordings, local_recordings)
        
        if missing_folders:
            print(f"Missing folders locally: {missing_folders}")
        
        if mismatched_files:
            print(f"Folders with mismatched files: {mismatched_files}")
        
        if not missing_folders and not mismatched_files:
            print("Local folders are an exact replica of Zoom recordings.")        

        print("All recordings processed and uploaded successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
    

# Example Usage
if __name__ == "__main__":
    main_sync_check()