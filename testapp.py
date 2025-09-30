# app.py
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import url_for, jsonify
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
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask_mail import Mail, Message
from forms import RegistrationForm
from flask_socketio import SocketIO, emit 
from werkzeug.utils import secure_filename
import uuid 
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
# Add this block right after app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'False').lower() in ['true', '1', 'yes']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)
app.secret_key = SECRET_KEY
bcrypt = Bcrypt(app)
socketio = SocketIO(app)

client = MongoClient(MONGO_URI)
db = client["emotion_music_app"]
users_col = db["users"]
history_col = db["music_history"]
spotify_state_col = db["spotify_state"]
users_col.create_index("email", unique=True)
history_col.create_index("user_email")
spotify_state_col.create_index([("user_email", 1), ("playlist_id", 1)], unique=True)

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

# --- NEW: Reusable function to check Spotify status and refresh token ---
def _check_and_refresh_spotify_token(user_email):
    """
    Checks a user's Spotify token, refreshes if expired, and returns the current token.
    Returns a tuple: (token, is_premium_status)
    """
    user_data = users_col.find_one({"email": user_email})
    
    spotify_token = user_data.get("spotify_access_token")
    spotify_refresh = user_data.get("spotify_refresh_token")
    spotify_expires_at = user_data.get("spotify_expires_at")
    is_premium = user_data.get("is_spotify_premium", False)

    if not all([spotify_token, spotify_refresh, spotify_expires_at]):
        return None, is_premium

    if time.time() > spotify_expires_at:
        try:
            sp_oauth = get_spotify_oauth()
            new_token_info = sp_oauth.refresh_access_token(spotify_refresh)
            
            spotify_token = new_token_info["access_token"] # Use the new token
            
            users_col.update_one(
                {"email": user_email},
                {"$set": {
                    "spotify_access_token": new_token_info["access_token"],
                    "spotify_expires_at": new_token_info["expires_at"]
                }}
            )
            logging.info(f"Successfully refreshed Spotify token for {user_email}")
        except Exception as e:
            logging.error(f"Could not refresh Spotify token for {user_email}: {e}")
            return None, is_premium
    
    # After ensuring token is valid, we can also re-check premium status
    try:
        sp = spotipy.Spotify(auth=spotify_token)
        user_info = sp.current_user()
        is_premium = user_info.get('product') == 'premium'
        users_col.update_one({"email": user_email}, {"$set": {"is_spotify_premium": is_premium}})
    except Exception:
        # If this fails, we can rely on the last known status from the DB
        pass

    return spotify_token, is_premium
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
            "default_language": form.language.data,
            "player_lock": {"status": "none", "timestamp": 0},
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
            users_col.update_one(                                      
                {"email": email},                                       
                {"$set": {"player_lock": {"status": "none", "timestamp": 0}}}   
            )

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
    user_data = users_col.find_one({"email": email}) or {}

    # --- EXISTING LOGIC (No changes here) ---
    history = list(history_col.find({
        "user_email": email,
        "type": {"$in": ["local_play", "spotify_play"]}
    }).sort('_id', -1))
    stats = {}
    for entry in history:
        emo = entry.get("emotion", "neutral")
        stats[emo] = stats.get(emo, 0) + 1

    spotify_linked = False
    expires_at = user_data.get("spotify_expires_at")
    access_token = user_data.get("spotify_access_token")
    if access_token and expires_at and time.time() < expires_at:
        spotify_linked = True

    # --- NEW: Get the profile picture filename ---
    user_profile_pic = user_data.get("profile_pic", None)

    return render_template(
        "dashboard.html",
        username=user_data.get("username"),
        email=email,
        history=history,
        stats=stats,
        user_spotify_linked=spotify_linked,
        user_profile_pic=user_profile_pic  # Pass filename to the template
    )

# ----- Vitals Player Route -----
@app.route("/vitals_player")
def vitals_player():
    if "user" not in session:
        return redirect(url_for("login"))
    
    user_email = session["user"]["email"]
    user_data = users_col.find_one({"email": user_email})
    default_language = user_data.get("default_language", "english")
    
    # --- MODIFIED: Use the new helper function for a consistent check ---
    spotify_token, _ = _check_and_refresh_spotify_token(user_email)
    is_spotify_connected = True if spotify_token else False
    # -----------------------------------------------------------------
    
    return render_template(
        "vitals_player.html", 
        username=session["user"]["username"], 
        default_language=default_language,
        is_spotify_connected=is_spotify_connected  # Pass the reliable status
    )

# ----- Edit Profile Route -----
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    user_data = users_col.find_one({"email": user_email})

    if request.method == "POST":
        # --- PROFILE PICTURE LOGIC ---
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '' and allowed_file(file.filename):
                # Create a unique filename to prevent conflicts
                filename_ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4()}.{filename_ext}"

                # Delete old picture if it exists
                old_pic = user_data.get("profile_pic")
                if old_pic:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], old_pic))
                    except OSError as e:
                        print(f"Error deleting old profile picture: {e}")

                # Save the new file and update the database
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                users_col.update_one({"email": user_email}, {"$set": {"profile_pic": unique_filename}})
                flash("Profile picture updated!", "success")

        # --- EXISTING PROFILE UPDATE LOGIC ---
        new_username = request.form["username"]
        new_email = request.form["email"]
        new_password = request.form["password"]
        new_language = request.form["language"]

        if new_email != user_email and users_col.find_one({"email": new_email}):
            flash("That email address is already in use.", "danger")
            return render_template("edit_profile.html", user=user_data)

        update_data = {
            "username": new_username,
            "email": new_email,
            "default_language": new_language
        }
        if new_password:
            hashed_pw = bcrypt.generate_password_hash(new_password).decode("utf-8")
            update_data["password"] = hashed_pw

        users_col.update_one({"email": user_email}, {"$set": update_data})

        session["user"]["username"] = new_username
        session["user"]["email"] = new_email
        session.modified = True

        flash("Profile details updated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_profile.html", user=user_data)

# Add this entire function to app.py

# REPLACE your existing delete_profile_pic function with this one

@app.route("/delete_profile_pic", methods=["POST"])
def delete_profile_pic():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    user_data = users_col.find_one({"email": user_email})
    
    profile_pic_filename = user_data.get("profile_pic")
    
    if profile_pic_filename:
        # 1. Delete the file from the server
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], profile_pic_filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as e:
            print(f"Error deleting profile picture file: {e}")
            flash("An error occurred while deleting the picture.", "danger")
            return redirect(url_for('edit_profile'))
            
        # 2. Remove the field from the database
        users_col.update_one(
            {"email": user_email},
            {"$unset": {"profile_pic": ""}}
        )
        flash("Profile picture has been deleted.", "success")
        
    return redirect(url_for('edit_profile'))

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
    # NEW: Release any web player locks on logout
    if "user" in session:
        users_col.update_one(
            {"email": session["user"]["email"], "player_lock.status": "web"},
            {"$set": {"player_lock": {"status": "none", "timestamp": 0}}}
        )
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
    
    # --- LOCKING MECHANISM (No changes here) ---
    lock = user_data.get("player_lock", {"status": "none", "timestamp": 0})
    is_stale = (time.time() - lock.get("timestamp", 0)) > 60 

    if lock["status"] != "none" and not is_stale:
        flash(f"Another player ({lock['status']} mode) is already active. Please close it first.", "danger")
        return redirect(url_for("dashboard"))

    users_col.update_one(
        {"email": user_email},
        {"$set": {"player_lock": {"status": "desktop", "timestamp": time.time()}}}
    )
    # --- END LOCKING MECHANISM ---
    
    default_language = user_data.get("default_language", "english")
    
    # --- MODIFIED: Use the new helper function for a consistent and clean check ---
    spotify_token, is_premium = _check_and_refresh_spotify_token(user_email)

    # After the check, we get the latest user_data to pass the refresh token and expiry date
    # This ensures that if the token was refreshed, we pass the new details.
    latest_user_data = users_col.find_one({"email": user_email}) 
    spotify_refresh = latest_user_data.get("spotify_refresh_token")
    spotify_expires_at = latest_user_data.get("spotify_expires_at")
    # --- END OF MODIFICATION ---

    subprocess.Popen([
        sys.executable, "main.py",
        user_email, 
        default_language,
        spotify_token or "",
        spotify_refresh or "",
        str(spotify_expires_at or 0),
        str(is_premium) # Pass premium status as the 6th argument
    ])

    flash("Camera Music Player launched!", "success")
    return redirect(url_for("dashboard"))


# --- NEW API ROUTES FOR VITALS PLAYER LOCAL MUSIC RESUME ---

# --- NEW API ROUTES FOR VITALS PLAYER LOCAL MUSIC RESUME ---

@app.route('/local-music/get-resume-state', methods=['GET'])
def get_local_resume_state():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_email = session["user"]["email"]
    language = request.args.get('language')
    emotion = request.args.get('emotion')

    if not all([language, emotion]):
        return jsonify({"error": "Missing language or emotion"}), 400

    # We look for a special record in the history collection
    doc = history_col.find_one({
        "user_email": user_email,
        "type": "local_resume",
        "language": language,
        "emotion": emotion
    })

    if doc and "last_song_index" in doc:
        return jsonify({"index": doc["last_song_index"]})
    else:
        # If no record exists, start from the beginning of the playlist
        return jsonify({"index": 0})

@app.route('/local-music/log-resume-state', methods=['POST'])
def log_local_resume_state():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json()
    user_email = session["user"]["email"]

    # Update or create a record for this specific playlist
    history_col.update_one(
        {
            "user_email": user_email,
            "type": "local_resume",
            "language": data.get("language"),
            "emotion": data.get("emotion")
        },
        {
            "$set": {
                "last_song_index": data.get("index"),
                "last_song_name": data.get("song_name")
            }
        },
        upsert=True # This creates the document if it doesn't exist
    )
    return jsonify({"status": "success"})

# --- END OF NEW ROUTES ---

# --- END OF NEW ROUTES ---

@app.route("/get_music_recommendation", methods=['POST'])
def get_music_recommendation():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    emotion = (data.get('emotion') or '').strip().lower()
    language = (data.get('language') or '').strip().lower()
    mode = data.get('mode')

    # --- Spotify Mode ---
    if mode == 'Spotify':
        # Use the reliable token check function
        token, _ = _check_and_refresh_spotify_token(session["user"]["email"])
        if not token:
            return jsonify({"error": "Spotify token invalid or expired"}), 400

        try:
            sp = spotipy.Spotify(auth=token)
        except Exception as e:
            return jsonify({"error": f"Spotify init error: {str(e)}"}), 500

        LANGUAGE_SYNONYMS = {
            "english": ["english", "hollywood"], "hindi": ["hindi", "bollywood"],
            "malayalam": ["malayalam", "mollywood"], "tamil": ["tamil", "kollywood"],
        }
        EMOTION_SYNONYMS = {
            "happy": ["happy", "joy", "positive", "vibes", "energetic"],
            "sad": ["sad", "melancholy", "blue", "down"],
            "angry": ["angry", "rage", "furious"], "neutral": ["neutral", "calm", "chill", "relaxed"],
        }
        lang_keywords = LANGUAGE_SYNONYMS.get(language, [language])
        emo_keywords = EMOTION_SYNONYMS.get(emotion, [emotion])

        query_variants = [f"{language} {emotion}", f"{emotion} {language}", f"{language} {emotion} playlist"]
        candidate_ids = set()
        for q in query_variants:
            try:
                results = sp.search(q=q, type="playlist", limit=10)
                items = results.get("playlists", {}).get("items", []) or []
                for p in items:
                    if p and p.get("id"):
                        candidate_ids.add(p.get("id"))
            except Exception as e:
                app.logger.error("Spotify search error for '%s': %s", q, e)

        valid_candidates = []
        for pid in list(candidate_ids)[:15]:
            try:
                details = sp.playlist(pid, fields="id,uri,name,description,followers,external_urls")
                text = f"{(details.get('name') or '').lower()} {(details.get('description') or '').lower()}"
                if any(k in text for k in lang_keywords) and any(k in text for k in emo_keywords):
                    valid_candidates.append(details)
            except Exception as e:
                app.logger.error("Error fetching playlist details for %s: %s", pid, e)

        if valid_candidates:
            best = max(valid_candidates, key=lambda p: p.get("followers", {}).get("total", 0))
            return jsonify({
                "type": "spotify",
                "name": best.get("name", "Playlist"),
                "url": best.get("external_urls", {}).get("spotify"),
                "followers": best.get("followers", {}).get("total", 0),
                "id": best.get("id"),
                "uri": best.get("uri")
            })

        # Fallback if the main search yields no valid candidates
        try:
            results = sp.search(q=f"{emotion} playlist", type="playlist", limit=1)
            items = results.get("playlists", {}).get("items", []) or []
            if items:
                pid = items[0]["id"]
                details = sp.playlist(pid, fields="id,uri,name,followers,external_urls")
                return jsonify({
                    "type": "spotify",
                    "name": details.get("name", "Playlist"),
                    "url": details.get("external_urls", {}).get("spotify"),
                    "followers": details.get("followers", {}).get("total", 0),
                    "id": details.get("id"),
                    "uri": details.get("uri")
                })
        except Exception as e:
            app.logger.error("Final fallback Spotify search failed: %s", e)

        return jsonify({"error": f"No Spotify playlists found for {language} {emotion}"}), 404

    # --- Local Mode ---
    elif mode == 'Local':
        base_path = os.path.join('static', 'music', language, emotion)
        if not os.path.isdir(base_path):
            return jsonify({"type": "local", "tracks": []})
        tracks = []
        for fname in sorted(os.listdir(base_path)):
            if fname.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                tracks.append({
                    "name": os.path.splitext(fname)[0],
                    "path": url_for('static', filename=f"music/{language}/{emotion}/{fname}")
                })
        return jsonify({"type": "local", "tracks": tracks})
    else:
        return jsonify({"error": "Unknown mode"}), 400



@app.route("/log_vitals_history", methods=['POST'])
def log_vitals_history():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_email = session["user"]["email"]

    record = {
        "user_email": user_email,
        "language": data.get("language"),
        "emotion": data.get("emotion"),
        "detection_mode": "vitals",
        "type": "spotify_play" if data.get("playlist_name") else "local_play",
        "song_name": data.get("song_name"),
        "playlist_name": data.get("playlist_name"),
    }
    history_col.insert_one(record)
    return jsonify({"status": "success"}), 200

# --- END OF VITALS PLAYER API ROUTES ---


# ----- Spotify Login -----
@app.route("/spotify_login")
def spotify_login():
    if "user" not in session:
        return redirect(url_for("login"))

    scope = (
        "user-read-playback-state user-modify-playback-state "
        "user-read-private user-read-email "
        "playlist-read-private playlist-read-collaborative"
    )
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

        # --- NEW: Check for premium status and save it ---
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_info = sp.current_user()
        is_premium = user_info.get('product') == 'premium'
        # ------------------------------------------------

        # --- MODIFIED: Added is_spotify_premium to the update ---
        users_col.update_one(
            {"email": user_email},
            {"$set": {
                "spotify_access_token": token_info["access_token"],
                "spotify_refresh_token": token_info["refresh_token"],
                "spotify_expires_at": token_info["expires_at"],
                "is_spotify_premium": is_premium # Save the user's premium status
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
            "spotify_expires_at": "",
            "is_spotify_premium": "" # Also remove the premium flag
        }}
    )

    flash("Spotify account unlinked successfully.", "info")
    return redirect(url_for("dashboard"))

# ----------------------
# Run Flask
# ----------------------
# --- NEW VITALS PLAYER & LOCKING API ROUTES ---

# --- NEW: API routes for saving/loading Spotify playback state ---

@app.route("/log_spotify_state", methods=["POST"])
def log_spotify_state():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data or not data.get("playlist_id") or not data.get("track_uri"):
        return jsonify({"error": "Missing required data"}), 400

    user_email = session["user"]["email"]
    
    spotify_state_col.update_one(
        {"user_email": user_email, "playlist_id": data["playlist_id"]},
        {
            "$set": {
                "track_uri": data["track_uri"],
                "progress_ms": data.get("progress_ms", 0),
                "timestamp": time.time()
            }
        },
        upsert=True
    )
    return jsonify({"status": "success"}), 200

@app.route("/get_spotify_state/<playlist_id>", methods=["GET"])
def get_spotify_state(playlist_id):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_email = session["user"]["email"]
    
    state = spotify_state_col.find_one(
        {"user_email": user_email, "playlist_id": playlist_id}
    )
    
    if state:
        # Convert ObjectId to string for JSON serialization
        state['_id'] = str(state['_id'])
        return jsonify(state)
    else:
        return jsonify({}), 404 # Return empty object if no state found
        
# --- END OF NEW API ROUTES ---

# --- NEW API ROUTES FOR VITALS PLAYER SPOTIFY CONTROL ---

@app.route("/spotify/devices", methods=["GET"])
def get_spotify_devices():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    token, is_premium = _check_and_refresh_spotify_token(session["user"]["email"])
    if not token or not is_premium:
        return jsonify({"devices": []})

    try:
        sp = spotipy.Spotify(auth=token)
        devices = sp.devices()
        return jsonify(devices or {"devices": []})
    except Exception as e:
        logging.error(f"Could not get Spotify devices: {e}")
        return jsonify({"error": "Failed to get devices"}), 500

@app.route("/spotify/play", methods=["POST"])
def spotify_play():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    token, is_premium = _check_and_refresh_spotify_token(session["user"]["email"])
    if not token or not is_premium:
        return jsonify({"error": "Premium required"}), 403

    data = request.get_json()
    device_id = data.get("device_id")
    context_uri = data.get("context_uri") # e.g., playlist URI
    offset = data.get("offset") # e.g., {"uri": "track_uri"}
    position_ms = data.get("position_ms", 0)

    try:
        sp = spotipy.Spotify(auth=token)
        sp.start_playback(
            device_id=device_id,
            context_uri=context_uri,
            offset=offset,
            position_ms=position_ms
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Spotify start_playback error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/spotify/player-action/<action>", methods=["POST"])
def spotify_player_action(action):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    token, is_premium = _check_and_refresh_spotify_token(session["user"]["email"])
    if not token or not is_premium:
        return jsonify({"error": "Premium required"}), 403

    device_id = request.get_json().get("device_id")
    try:
        sp = spotipy.Spotify(auth=token)
        if action == 'pause':
            sp.pause_playback(device_id=device_id)
        elif action == 'resume':
            sp.start_playback(device_id=device_id)
        elif action == 'next':
            sp.next_track(device_id=device_id)
        elif action == 'previous':
            sp.previous_track(device_id=device_id)
        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Spotify action '{action}' error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/spotify/current-playback", methods=["GET"])
def get_current_playback():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    token, _ = _check_and_refresh_spotify_token(session["user"]["email"])
    if not token:
        return jsonify(None)
    
    try:
        sp = spotipy.Spotify(auth=token)
        playback = sp.current_playback()
        return jsonify(playback)
    except Exception as e:
        return jsonify(None)

# --- END OF NEW VITALS PLAYER API ROUTES ---

def map_vitals_to_emotion(bpm, hrv):
    """Maps BPM and HRV to an emotional state."""
    if bpm > 100 and hrv < 25: return "angry"
    if bpm > 90 and hrv > 40: return "happy"
    if bpm < 70 and hrv < 30: return "sad"
    return "neutral"

 
@socketio.on('connect')
def handle_connect():
    print('Web client connected to WebSocket')

@socketio.on('disconnect')
def handle_disconnect():
    print('Web client disconnected')

# This is a separate channel for your ESP32 hardware to connect to
@socketio.on('connect', namespace='/hardware')
def handle_hardware_connect():
    print(f'Hardware client connected: {request.sid}')

# This function will listen for 'vitals_update' messages from your ESP32
@socketio.on('vitals_update', namespace='/hardware')
def handle_vitals_update(data):
    """
    Receives data from ESP32 and broadcasts it to the web client.
    The ESP32 should send data like: {'bpm': 85, 'hrv': 45}
    """
    print(f"Received vitals from hardware: {data}")

    # Use your existing function to figure out the emotion
    emotion = map_vitals_to_emotion(data.get('bpm', 0), data.get('hrv', 0))

    # Prepare the final data to send to the webpage
    payload = {
        'bpm': data.get('bpm'),
        'hrv': data.get('hrv'),
        'detected_emotion': emotion
    }

    # Broadcast this payload to the vitals_player.html webpage
    socketio.emit('vitals_from_server', payload, namespace='/hardware')

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5000
    print(f"🚀 Your Flask app is running at: http://{host}:{port}/")
    socketio.run(app, host=host, port=port, debug=True)