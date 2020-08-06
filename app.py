# Python standard libraries
import json
import os
from datetime import date

# Third-party libraries
from flask import Flask, redirect, request, url_for, render_template
from oauthlib.oauth2 import WebApplicationClient
import requests

'''
grades is indexed this way: grades[Branch][Year]
grades[Branch][Year] -> Python list of csv strings

note: this could be obsolete if lot of records are there

TODO: Query from db instead of reading from file into memory
'''
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

    today = date.today()
    yr = today.year%100
    if today.month >= 6:
        yr-=1
    yr -= year
    email_col = 1 # this has to be manually updated according to the dataset
    sub_start_id = 2 # this is where the grades start
    if branch == 'C':
        #  grades[0]
        br = 0
    else:
        #  grades[1]
        br = 1
    header = grades[br][yr][0].strip().split(',')
    for row in grades[br][yr]:
        if row.strip().split(',')[email_col] == email:
            for i in range(sub_start_id, len(header)):
                results[header[i]] = row.strip().split(',')[i]
            return results

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
        email2roll = open('./email_roll.csv').readlines()
        for item in email2roll:
            em, rno = item.split(',')
            if em == user['email']:
                user['rollno'] = rno
                break

        if user['rollno'] == '':
            # means they logged in from some other mail id
            return (
                '<p>Please login with your institue mail id</p>'
                '<a href="/logout" class="btn btn-primary">Logout</a>'
            )
        year = int(user['rollno'][3:5])
        branch = user['rollno'][0].upper()
        results = fetch_results(branch.upper(), year, user['email'])
        if (len(results) == 0):
            return '<h2>Error has occurred. Please contact the class coordinator</h2>'
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
