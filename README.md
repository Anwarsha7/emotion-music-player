# AuraTune - Music That Feels What You Feel

[![MIT License](https://img.shields.io/github/license/Anwarsha7/emotion-music-player?style=for-the-badge)](https://github.com/Anwarsha7/emotion-music-player/blob/main/LICENSE)
![GitHub last commit](https://img.shields.io/github/last-commit/Anwarsha7/emotion-music-player?style=for-the-badge)
![GitHub repo size](https://img.shields.io/github/repo-size/Anwarsha7/emotion-music-player?style=for-the-badge)

AuraTune is an intelligent music player that uses AI to create personalized playlists based on your real-time emotional state. This final year project demonstrates the intersection of artificial intelligence, web development, and user experience to deliver music that truly resonates with your mood.

![AuraTune Desktop Player](screenshots/camera-player.png)

---

## 📸 Screenshots

Here's a look at the AuraTune application, from the landing page to the different player interfaces.

![Landing Page](screenshots/landing.png)
*The official landing page for AuraTune.*

![User Dashboard](screenshots/dashboard.png)
*The personalized user dashboard after logging in.*

![Vitals Player](screenshots/vitals-player.png)
*The web-based player that uses biometric data from hardware.*

---

## ✨ Key Features

- **AI Emotion Detection:** Utilizes a webcam to perform real-time facial emotion analysis (Happy, Sad, Angry, Neutral) using the DeepFace library.
- **Biometric Sensing Mode:** A web-based player that connects via WebSockets to hardware to generate playlists from live BPM and HRV data.
- **Dynamic Playlists:** Automatically curates playlists from either local music files or a Spotify account.
- **Spotify Integration:** Securely links to Spotify to unlock mood-based playlists, supporting both Free and Premium users.
- **Personalized Dashboard:** Track your listening history and view statistics on your most detected emotions over time.
- **Voice Commands:** Control the desktop player with voice commands for playback, volume, and mode selection.

## 🛠️ Tech Stack

- **Backend:** Flask, Flask-SocketIO
- **Frontend:** HTML, CSS, JavaScript, Jinja2
- **Desktop Player:** Python, CustomTkinter, OpenCV
- **AI/ML:** TensorFlow, DeepFace
- **Database:** MongoDB
- **APIs:** Spotify API, Cloudinary API

## 🚀 Setup and Installation

Follow these steps to get the project running locally.

**1. Clone the Repository**
```bash
git clone [https://github.com/Anwarsha7/emotion-music-player.git](https://github.com/Anwarsha7/emotion-music-player.git)
cd emotion-music-player
```

**2. Create and Activate a Virtual Environment**
```bash
# Create the environment
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

**3. Install Dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure Environment Variables**

Create a file named `.env` in the root of the project and fill in your own credentials. Use the following template:

```env
# MongoDB Connection String
MONGO_URI="your_mongodb_connection_string"

# A long, random string for Flask's secret key
SECRET_KEY="a_very_long_and_random_secret_key"

# Spotify API Credentials
SPOTIPY_CLIENT_ID="your_spotify_client_id"
SPOTIPY_CLIENT_SECRET="your_spotify_client_secret"
SPOTIPY_REDIRECT_URI="[http://127.0.0.1:5000/callback](http://127.0.0.1:5000/callback)"

# Gmail Credentials for Feedback & Password Reset
MAIL_SERVER="smtp.gmail.com"
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME="your_gmail_address@gmail.com"
MAIL_PASSWORD="your_gmail_app_password"

# Cloudinary Credentials for Profile Pictures
CLOUDINARY_CLOUD_NAME="your_cloudinary_cloud_name"
CLOUDINARY_API_KEY="your_cloudinary_api_key"
CLOUDINARY_API_SECRET="your_cloudinary_api_secret"
```

**5. Run the Application**
```bash
python app.py
```
The web application will be available at `http://127.0.0.1:5000`.

## 👤 About the Project

This was developed as my final year project. I am passionate about the intersection of AI and user experience, and AuraTune is the culmination of my effort to build a smarter, more intuitive music player.
