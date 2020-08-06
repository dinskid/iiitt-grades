# Python standard libraries
import json
import os

# Third-party libraries
from flask import Flask, redirect, request, url_for, render_template
from oauthlib.oauth2 import WebApplicationClient
import requests

# Load grades into memory
grades = [[None, None, None, None], [None, None, None, None]]

grades[0][0] = open('./cse19.csv').readlines()
grades[0][1] = open('./cse18.csv').readlines()
grades[0][2] = open('./cse17.csv').readlines()
grades[0][3] = open('./cse16.csv').readlines()
grades[1][0] = open('./ece19.csv').readlines()
grades[1][1] = open('./ece18.csv').readlines()
grades[1][2] = open('./ece17.csv').readlines()
grades[1][3] = open('./ece16.csv').readlines()

results = {}
for person in grades:
    fields = person.strip().split(',')
    roll, email = fields[0], fields[1]
    results[email] = fields[2:]

def fetch_results(branch, year, email):
    '''
    Input format:
    branch: String (CSE|ECE)
    year: int (19|18|17|16)
    email: String (college given email address)

    Output:
    results: Dict (with sub code as key and grade as value)
    Also, passed, failed are part of results
    '''
    results = {}
    br = -1
    yr = 19-year
    email_row = 1
    if branch == 'C':
        #  grades[0]
        br = 0
    else:
        #  grades[1]
        br = 1
    for row in grades[br][yr]:
        if row.strip().split(',')[email_row] == email:
            for i in range(4, len(header)-7):
                results[header[i]] = row[i]

    return results

# Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
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
    'branch': '',
}

@app.route('/')
def index():
    return render_template('home.html', logged_in=logged_in, user=user)

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
        name = userinfo_response.json()['name']
    else:
        return "User email not verified", 400

    global logged_in, user
    logged_in = True
    user['name'] = name
    user['email'] = email
    if email.split('@')[0][-1] == 'c':
        user['branch'] = 'CSE'
    else:
        user['branch'] = 'ECE'
    return redirect(url_for('index'))

@app.route('/getresults')
def getresults():
    if logged_in:
        front, rear = user['email'].split('@')
        if rear != 'iiitt.ac.in':
            # means they logged in from some other mail id
            return (
                '<p>Please login with your institue mail id</p>'
                '<a href="/logout" class="btn btn-primary">Logout</a>'
            )
        year = int(front[-2:])
        branch = front[-3]
        results = fetch_results(branch.upper(), year, user['email'])
        return render_template('results.html', user=user, results=results)
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
