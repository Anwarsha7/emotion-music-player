# 🎵 AuraTune - Music That Feels What You Feel

[![MIT License](https://img.shields.io/github/license/Anwarsha7/emotion-music-player?style=for-the-badge)](https://github.com/Anwarsha7/emotion-music-player/blob/main/LICENSE)
![GitHub last commit](https://img.shields.io/github/last-commit/Anwarsha7/emotion-music-player?style=for-the-badge)
![GitHub repo size](https://img.shields.io/github/repo-size/Anwarsha7/emotion-music-player?style=for-the-badge)

![Python](https://img.shields.io/badge/Python-3.9-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask)
![TensorFlow](https://img.shields.io/badge/TensorFlow-FF6F00?style=for-the-badge&logo=tensorflow)
![Spotify](https://img.shields.io/badge/Spotify-1DB954?style=for-the-badge&logo=spotify)
![MongoDB](https://img.shields.io/badge/MongoDB-4DB33D?style=for-the-badge&logo=mongodb)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-008080?style=for-the-badge)

---

AuraTune is an intelligent music player that uses **AI-driven emotion detection** and **biometric signals** to create personalized playlists in real time.  
Developed as my **Final Year B.Tech Project**, AuraTune represents the intersection of **artificial intelligence, human emotions, and immersive user experience**.

![AuraTune Desktop Player](screenshots/camera-player.png)

 ## 📸 Screenshots

![Landing Page](screenshots/landing.png)  
*The official landing page for AuraTune.*

![User Dashboard](screenshots/dashboard.png)  
*The personalized user dashboard after logging in.*

![Vitals Player](screenshots/vitals-player.png)  
*The web-based player that uses biometric data from hardware.*

---

## ✨ Key Features

AuraTune has **three powerful modes of interaction**:

### 🎭 Emotion Detection Mode
- Real-time facial emotion analysis via **DeepFace** (Happy, Sad, Angry, Neutral).
- Webcam-powered detection for dynamic playlist curation.

### ❤️ Biometric Sensing Mode
- Web-based vitals player connected via **Flask-SocketIO**.  
- Uses **HRV (Heart Rate Variability)** & **BPM** from hardware sensors.  
- Generates playlists that match physiological states.

### 🎶 Music Playback Modes
- **Local Mode:** Play curated playlists from local files.  
- **Spotify Mode:** Integrates with Spotify (Free & Premium accounts).  
- Dynamic mood-based playlist generation with seamless playback.  

Additional features:
- 🗂 Personalized dashboard with emotion statistics & history  
- 🎙 Voice commands for desktop player control  
- 🔒 Secure authentication & profile management  

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    A[Camera Input] --> B[DeepFace Model]
    B --> C[Emotion Detected]
    C --> D[Playlist Generator]
    D --> E[Spotify API / Local Files]

    F[Hardware Vitals] --> G[Flask-SocketIO]
    G --> H[Biometric Data Processing]
    H --> D


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

Create a file named `.env` in the root of the project and fill in your own credentials. Use the `.env.example` file as a template.

**5. Run the Application**
```bash
python app.py
```
The web application will be available at `http://127.0.0.1:5000`.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Please feel free to fork this repo and submit a pull request. For more details, see the [CONTRIBUTING.md](CONTRIBUTING.md) file.

## 🔭 Future Scope
This project has a strong foundation with many possibilities for future development:
- **🎧 More Music Integrations:** Adding support for other services like Apple Music or YouTube Music.
- **📱 Mobile Application:** Developing a cross-platform mobile app version using a framework like Flutter or React Native.
- **🧠 Expanded Emotion Model:** Training or integrating a model to recognize a wider range of emotions, such as Fear, Surprise, and Disgust.

## 👤 About the Project

This was developed as my final year project. I am passionate about the intersection of AI and user experience, and AuraTune is the culmination of my effort to build a smarter, more intuitive music player.

## 🙏 Acknowledgements
This project would not have been possible without these incredible open-source libraries:
- [DeepFace](https://github.com/serengil/deepface) for its comprehensive facial attribute analysis.
- [Spotipy](https://spotipy.readthedocs.io/) for its powerful and easy-to-use Spotify API wrapper.
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for enabling modern and beautiful Python GUIs.
