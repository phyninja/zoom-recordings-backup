# zoom-recordings-backup
Backs up Zoom Cloud Recordings to Google Drive

## Setup Instructions


### 1. Install Python (Windows)
- Ensure you have Python installed on your system. You can download it from [python.org](https://www.python.org/downloads/windows/). During installation, ensure that you check the box that says "Add Python to PATH."

### 2. Install Required Dependencies
- After installing Python, navigate to the project directory and run the following command to install all the required Python packages:
```bash
pip install -r requirements.txt
```

### 3. Obtain Zoom API Credentials
To access Zoom recordings, you will need to create/use the already-created Zoom app and get the necessary credentials.
To use the already-created Zoom app, visit the Zoom Marketplace using the Zoom account vivek@codingal.com and get the `Client ID` and `Client Secret` from the app *Codingal Cloud Recordings Backup*

### 4. Set Up the Configuration File
1. Copy the example configuration file:
```bash
cp config.example.json config.json
```

2. Fill in the real values in `config.json` as per your setup:
- `base_dir`: The directory where your Zoom recordings are stored.
- `start_date` and `end_date`: The date range for fetching recordings.
- `access_token_refresh_frequency`: The frequency in seconds to refresh the access token (default is 1800 seconds).

### 5. Setup Environment Variables
- Create a `.env` file in the root of your project based on the provided `.env.example`.
- Populate it with your own credentials, like `CLIENT_ID`, `CLIENT_SECRET`, `USER_ID`, etc.

### 6. Generate Access and Refresh Tokens
- After filling out config.json and creating the .env file as instructed, run the following script to generate and print the ACCESS_TOKEN and REFRESH_TOKEN in the terminal:
```bash
python import_requests.py
```
- Use this information to complete the ACCESS_TOKEN and REFRESH_TOKEN fields in the .env file.

### 7. Download Zoom Recordings to Google Drive
- To back up Zoom recordings to your local Google Drive folder, run the following command:
```bash
python zoom_recordings.py
```

### 8. Verify Sync Quality
- After the Zoom recordings have been downloaded, run the following script to verify the quality of the local sync against the recordings on Zoom:
```bash
python sync_check.py
```
This script will check for any missing or mismatched files between the local folders and the Zoom recordings.

