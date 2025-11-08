from flask import Flask, request, redirect
import requests

app = Flask(__name__)

CLIENT_ID = "Cf1a70a56b56f4b0266b99a374b2e35907ef80588430c8c5e357378a0211fc531"
CLIENT_SECRET = "e1a92156f6ec6d94b60732c273c8e7c6a69bf08eef4d14f9a00eb65317c58eec"
REDIRECT_URI = "http://localhost:5000/callback"

SCOPES = "vonk:oproepen_lezen vonk:mensen_lezen"
AUTH_URL = (
    f"https://webexapis.com/v1/authorize?client_id={CLIENT_ID}"
    f"&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    f"&scope={SCOPES.replace(' ', '%20')}"
    f"&state=test123"
)


@app.route('/')
def login():
    print("DEBUG: Stuur user naar Webex autorisatie-URL:")
    print(AUTH_URL)
    return redirect(AUTH_URL)

@app.route('/callback')
def callback():
    print("DEBUG: Callback route aangeroepen.")
    if 'error' in request.args:
        error = request.args['error']
        error_description = request.args.get('error_description', '')
        print(f"Webex error: {error} - {error_description}")
        return f"Webex error: {error} - {error_description}", 400

    code = request.args.get('code')
    if not code:
        print("DEBUG: Geen code ontvangen in callback.")
        return "Geen code ontvangen van Webex. Probeer opnieuw.", 400

    print("DEBUG: Authorization code ontvangen:", code)
    token_resp = requests.post(
        "https://webexapis.com/v1/access_token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
    )
    print("DEBUG: Token response status code:", token_resp.status_code)
    token_json = token_resp.json()
    print("DEBUG: Token response inhoud:", token_json)

    if "access_token" not in token_json:
        return f"Webex token fout: {token_json}", 400

    access_token = token_json["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    print("DEBUG: Verzoeken om mensen/contacten...")
    people_resp = requests.get("https://webexapis.com/v1/people", headers=headers)
    print("DEBUG: People response:", people_resp.status_code, people_resp.text)

    print("DEBUG: Verzoeken om actieve calls...")
    calls_resp = requests.get("https://webexapis.com/v1/telephony/calls", headers=headers)
    print("DEBUG: Calls response:", calls_resp.status_code, calls_resp.text)

    return "Webex API getest! Kijk in je terminal voor alle debug output."

if __name__ == "__main__":
    app.run(port=5000, debug=True)
