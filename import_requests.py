import base64
import requests
import webbrowser
from flask import Flask, request
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Your Zoom App credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
TOKEN_URL = "https://zoom.us/oauth/token"

def encode_credentials(client_id, client_secret):
    credentials = f"{client_id}:{client_secret}"
    return base64.b64encode(credentials.encode()).decode()

# Step 1: Redirect user to Zoom for authorization
# Step 1: Redirect user to Zoom for authorization
@app.route('/')
def authorize_zoom():
    authorize_redirect_url = (
        f"https://zoom.us/oauth/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    )
    webbrowser.open(authorize_redirect_url)  # Open in browser
    return "Redirecting to Zoom for authorization..."

# Step 2: Handle the redirect and get the authorization code
@app.route('/redirect')
def get_auth_code():
    auth_code = request.args.get('code')
    if auth_code:
        # Exchange authorization code for access token
        token_data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        }
        headers = {
            "Authorization": f"Basic {encode_credentials(CLIENT_ID, CLIENT_SECRET)}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Make the request to get the access token
        response = requests.post(TOKEN_URL, headers=headers, data=token_data)
        
        # Print the entire response for debugging
        print(f"Token exchange response: {response.text}")
        
        if response.status_code == 200:
            try:
                token_info = response.json()
                access_token = token_info['access_token']
                refresh_token = token_info['refresh_token']
                print(f"Access Token: {access_token}")
                return f"Access Token Received: {access_token}"
                print(f"Refresh Token: {refresh_token}")
                return f"Refresh Token Received: {refresh_token}"
            except KeyError:
                return "Error: 'access_token' not found in the response."
        else:
            return f"Error getting access token: {response.status_code} {response.text}"
    return "No authorization code received."

if __name__ == '__main__':
    app.run(port=5000)
