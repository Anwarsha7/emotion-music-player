<div align="center">

# 🎵 AuraTune - Music That Feels What You Feel

**AuraTune is an intelligent music player that uses AI-driven emotion detection and biometric signals to create personalized playlists in real time. Developed as a Final Year B.Tech Project, AuraTune represents the intersection of artificial intelligence, human emotions, and an immersive user experience.**

</div>

<div align="center">

[![MIT License](https://img.shields.io/github/license/Anwarsha7/emotion-music-player?style=for-the-badge)](https://github.com/Anwarsha7/emotion-music-player/blob/main/LICENSE)
![GitHub last commit](https://img.shields.io/github/last-commit/Anwarsha7/emotion-music-player?style=for-the-badge)
![GitHub repo size](https://img.shields.io/github/repo-size/Anwarsha7/emotion-music-player?style=for-the-badge)

</div>

---

![AuraTune Desktop Player](screenshots/camera-player.png)

## ✨ Key Features

AuraTune offers a unique and interactive music experience through three powerful modes:

### 🎭 **Emotion Detection Mode**
-   **Real-time Facial Analysis**: Utilizes the **DeepFace** library to analyze facial expressions from a webcam and detect emotions like *Happy*, *Sad*, *Angry*, and *Neutral*.
-   **Dynamic Playlist Curation**: Automatically generates and plays music that matches your current emotional state.

### ❤️ **Biometric Sensing Mode**
-   **Real-time Vitals Monitoring**: Connects to hardware sensors via a web-based player using **Flask-SocketIO**.
-   **Physiology-Based Playlists**: Uses biometric data such as **Heart Rate Variability (HRV)** and **BPM** to curate playlists that align with your physiological state (e.g., calm music for a low heart rate).

### 🎶 **Flexible Music Playback**
-   **Local Playback**: Play mood-curated playlists directly from your local music library.
-   **Spotify Integration**: Seamlessly connect your Spotify account (both Free & Premium) to generate and play dynamic, mood-based playlists.

### **Additional Features**
-   **🗂️ Personalized Dashboard**: View your emotion statistics and playback history.
-   **🎙️ Voice Commands**: Control the desktop player hands-free.
-   **🔒 Secure Authentication**: Robust user login and profile management.

---

## 📸 Screenshots

<details>
<summary>Click to view screenshots</summary>

| Landing Page | User Dashboard | Vitals Player |
| :---: | :---: | :---: |
| ![Landing Page](screenshots/landing.png) | ![User Dashboard](screenshots/dashboard.png) | ![Vitals Player](screenshots/vitals-player.png) |
| *The official landing page for AuraTune.* | *The personalized user dashboard.* | *The web-based player using biometric data.* |

</details>

---

## 🏗️ System Architecture

AuraTune's architecture is designed to process user input from two primary sources—visual (camera) and physiological (hardware sensors)—to generate a curated music playlist.

```mermaid
graph TD
    subgraph Input Sources
        A[Camera Input]
        F[Hardware Vitals]
    end

    subgraph Processing Engine
        B[DeepFace Model]
        G[Flask-SocketIO Server]
        H[Biometric Data Processing]
        D[Playlist Generator]
    end

    subgraph Output
        E[Spotify API / Local Files]
    end

    A --> B --> C[Emotion Detected]
    F --> G --> H
    C --> D
    H --> D
    D --> E


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
