# app.py
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import url_for
from bson.objectid import ObjectId
from forms import RegistrationForm, RequestResetForm, ResetPasswordForm
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
import os
import subprocess
from dotenv import load_dotenv
import sys
from spotipy.oauth2 import SpotifyOAuth
from flask_mail import Mail, Message
from forms import RegistrationForm
# In app.py
import logging

# --- ADD THIS LOGGING CONFIGURATION ---
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# ------------------------------------
 
# Load environment variables
# ----------------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

# ----------------------
# Initialize Flask and Mongo
# ----------------------
app = Flask(__name__)
# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'False').lower() in ['true', '1', 'yes']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)
app.secret_key = SECRET_KEY
bcrypt = Bcrypt(app)

client = MongoClient(MONGO_URI)
db = client["emotion_music_app"]
users_col = db["users"]
history_col = db["music_history"]
users_col.create_index("email", unique=True)
history_col.create_index("user_email")

# In app.py

def get_reset_token(user, expires_sec=1800):
    s = Serializer(app.config['SECRET_KEY'])
    # The token is created with the user's ID
    return s.dumps({'user_id': str(user['_id'])})

def verify_reset_token(token):
    s = Serializer(app.config['SECRET_KEY'])
    try:
        # The token is loaded with a max age of 30 minutes (1800 seconds)
        data = s.loads(token, max_age=1800)
        user_id = data.get('user_id')
    except:
        return None
    # Find the user in the database with the ID from the token
    return users_col.find_one({'_id': ObjectId(user_id)})
# In app.py

def send_reset_email(user):
    token = get_reset_token(user)
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',  # Or use your MAIL_USERNAME
                  recipients=[user['email']])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)
# ----------------------
# Spotify OAuth helper
# ----------------------
def get_spotify_oauth(scope=None):
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=scope
    )

# ----------------------
# Routes
# ----------------------
@app.route("/")
def home():
    # if logged in -> dashboard, else show landing page
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

# ----- Register -----
# In app.py
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit(): # This checks if the form was submitted and is valid
        # Check if user already exists
        if users_col.find_one({"email": form.email.data}):
            flash("Email already registered!", "danger")
            return redirect(url_for("register"))

        # Hash the password and create the user
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        users_col.insert_one({
            "username": form.username.data,
            "email": form.email.data,
            "password": hashed_pw,
            "default_language": form.language.data
        })
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form=form) # Pass the form to the template

# ----- Login -----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users_col.find_one({"email": email})
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = {
                "username": user["username"],
                "email": user["email"]
            }
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html")

# In app.py

@app.route("/request_reset", methods=['GET', 'POST'])
def request_reset():
    if "user" in session: # If user is logged in, redirect them
        return redirect(url_for('dashboard'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = users_col.find_one({"email": form.email.data})
        if user:
            send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('request_reset.html', form=form)


@app.route("/reset_token/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if "user" in session: # If user is logged in, redirect them
        return redirect(url_for('dashboard'))
    user = verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token.', 'danger')
        return redirect(url_for('request_reset'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        users_col.update_one({"_id": user['_id']}, {"$set": {"password": hashed_pw}})
        flash('Your password has been updated! You are now able to log in.', 'success')
        return redirect(url_for('login'))
    
    # We will create reset_token.html in the next step
    return render_template('reset_token.html', form=form)
# ----- Dashboard -----
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    email = session["user"]["email"]
    username = session["user"]["username"]

    # Fetch listening history
    history = list(history_col.find({
        "user_email": email,
        "type": {"$in": ["local_play", "spotify_play"]}
    }).sort('_id', -1))

    # Compute emotion stats
    stats = {}
    for entry in history:
        emo = entry.get("emotion", "neutral")
        stats[emo] = stats.get(emo, 0) + 1

    # Fetch user document from DB
    user_data = users_col.find_one({"email": email}) or {}

    # Detect whether Spotify is linked
    # This is the new, smarter check
    spotify_linked = False
    expires_at = user_data.get("spotify_expires_at")
    access_token = user_data.get("spotify_access_token")

    if access_token and expires_at and time.time() < expires_at:
        spotify_linked = True

    return render_template(
        "dashboard.html",
        username=username,
        email=email,
        history=history,
        stats=stats,
        user_spotify_linked=spotify_linked
    )

# ----- NEW: Edit Profile Route -----
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    user_data = users_col.find_one({"email": user_email})

    if request.method == "POST":
        new_username = request.form["username"]
        new_email = request.form["email"]
        new_password = request.form["password"]
        new_language = request.form["language"]

        # Check if the new email is already taken by another user
        if new_email != user_email and users_col.find_one({"email": new_email}):
            flash("That email address is already in use.", "danger")
            return render_template("edit_profile.html", user=user_data)

        # Prepare update data
        update_data = {
            "username": new_username,
            "email": new_email,
            "default_language": new_language
        }

        # If a new password was entered, hash and include it
        if new_password:
            hashed_pw = bcrypt.generate_password_hash(new_password).decode("utf-8")
            update_data["password"] = hashed_pw

        # Update the database
        users_col.update_one({"email": user_email}, {"$set": update_data})

        # Update the session with new details
        session["user"]["username"] = new_username
        session["user"]["email"] = new_email
        session.modified = True

        flash("Profile updated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_profile.html", user=user_data)

@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    if request.method == "POST":
        name = request.form['name']
        email = request.form['email']
        message_body = request.form['message']

        msg = Message(
            subject=f"AuraTune Feedback from {name}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[app.config['MAIL_USERNAME']] # Send the email to yourself
        )
        msg.body = f"From: {name} <{email}>\n\n{message_body}"
        
        try:
            mail.send(msg)
            flash("Thank you for your feedback! It has been sent.", "success")
        except Exception as e:
            flash(f"Sorry, an error occurred: {str(e)}", "danger")

        # Redirect back to the landing page, to the contact section
        # Assumes your landing page route is named "home". Change if necessary.
        return redirect(url_for("home") + "#contact")

# ----- Logout -----
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# ----- Delete Music History -----
@app.route("/delete_history", methods=["POST"])
def delete_history():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    result = history_col.delete_many({"user_email": user_email})

    flash(f"Successfully deleted {result.deleted_count} history records.", "success")
    return redirect(url_for("dashboard"))

# ----- Launch Music Player -----
@app.route("/launch_app")
def launch_app():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    user_data = users_col.find_one({"email": user_email})
    default_language = user_data.get("default_language", "english")

    # Check Spotify tokens
    spotify_token = user_data.get("spotify_access_token")
    spotify_refresh = user_data.get("spotify_refresh_token")
    spotify_expires_at = user_data.get("spotify_expires_at")

    # If any token is missing, set them as empty
    if not spotify_token or not spotify_refresh or not spotify_expires_at:
        spotify_token = spotify_refresh = spotify_expires_at = ""
        flash("Spotify not connected. Spotify mode will be disabled.", "info")

    # Launch main.py with tokens
    subprocess.Popen([
        sys.executable, "main.py",
        user_email, default_language,
        spotify_token, spotify_refresh, str(spotify_expires_at)
    ])

    flash("Music Player launched!", "success")
    return redirect(url_for("dashboard"))


# ----- Spotify Login -----
@app.route("/spotify_login")
def spotify_login():
    if "user" not in session:
        return redirect(url_for("login"))

    scope = "user-read-playback-state user-read-private playlist-read-private playlist-read-collaborative"
    sp_oauth = get_spotify_oauth(scope)

    # Get the base URL first
    auth_url = sp_oauth.get_authorize_url()

    # Manually add the parameter to force the login dialog
    auth_url += "&show_dialog=true"

    return redirect(auth_url)

# ----- Spotify Callback -----
@app.route("/callback")
def spotify_callback():
    if "user" not in session:
        return redirect(url_for("login"))

    sp_oauth = get_spotify_oauth()
    code = request.args.get("code")

    if not code:
        flash("Spotify authentication failed: No authorization code received.", "danger")
        return redirect(url_for("dashboard"))

    try:
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        
        user_email = session["user"]["email"]

        users_col.update_one(
            {"email": user_email},
            {"$set": {
                "spotify_access_token": token_info["access_token"],
                "spotify_refresh_token": token_info["refresh_token"],
                "spotify_expires_at": token_info["expires_at"]
            }}
        )
        flash("Spotify account connected successfully!", "success")

    except Exception as e:
        logging.error(f"Spotify token exchange error: {e}")
        flash("An error occurred while connecting to Spotify. Please try again.", "danger")

    return redirect(url_for("dashboard"))

# ----- Unlink Spotify -----
@app.route("/unlink_spotify", methods=["POST"])
def unlink_spotify():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]

    users_col.update_one(
        {"email": user_email},
        {"$unset": {
            "spotify_access_token": "",
            "spotify_refresh_token": "",
            "spotify_expires_at": ""
        }}
    )

    flash("Spotify account unlinked successfully.", "info")
    return redirect(url_for("dashboard"))

# ----------------------
# Run Flask
# ----------------------
if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5000
    print(f"🚀 Your Flask app is running at: http://{host}:{port}/")
    app.run(host=host, port=port, debug=True)
