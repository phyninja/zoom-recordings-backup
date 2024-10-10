# zoom-recordings-backup
Backs up Zoom Cloud Recordings to Google Drive

## Setup Instructions
1. Copy the example configuration file:
```cp config.example.json config.json```

2. Fill in the real values in `config.json` as per your setup:
- `base_dir`: The directory where your Zoom recordings are stored.
- `start_date` and `end_date`: The date range for fetching recordings.
- `access_token_refresh_frequency`: The frequency in seconds to refresh the access token (default is 1800 seconds).
