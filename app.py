# Python standard libraries
import json
import os

# Third-party libraries
from flask import Flask, redirect, request, url_for
from oauthlib.oauth2 import WebApplicationClient
import requests

grades = open('./grades.csv').readlines()
grades = grades[1:]

results = {}
for person in grades:
    fields = person.strip().split(',')
    roll, email = fields[0], fields[1]
    results[email] = fields[2:]

# Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
print('GOOGLE_CLIENT_ID:', GOOGLE_CLIENT_ID)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# To check if somebody is logged in or not
logged_in = False
user = {
    'name': '',
    'rollno': '',
    'email': '',
}
@app.route('/')
def index():
    if logged_in:
        return (
            '<a class="button" href="/getresults">Download results</a>'
            '<br />'
            '<a class="button" href="/logout">Logout</a>'
        )
    else:
        return '<a href="/login">Login</a>'

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

@app.route('/login')
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@app.route('/login/callback')
def callback():
    code = request.args.get('code')
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg['token_endpoint']
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_endpoint=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_endpoint = google_provider_cfg['userinfo_endpoint']
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    print(userinfo_response.json())
    if userinfo_response.json().get('email_verified'):
        unique_id = userinfo_response.json()['sub']
        email = userinfo_response.json()['email']
        name = userinfo_response.json()['given_name']
    else:
        return "User email not verified", 400

    global logged_in, user
    logged_in = True
    user['name'] = name
    user['email'] = email
    return redirect(url_for('index'))

@app.route('/getresults')
def getresults():
    if logged_in:
        result = results.get(user['email'])
        if not result:
            # means they logged in from some other mail id
            return '<p>Please login with your institue mail id'
        return (
            '<p>{}</p>'.format(result)
        )
    else:
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    global logged_in, user
    for field in user:
        user[field] = ''
    logged_in = False

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run()
