import os
import pyttsx3
import cv2
import time
import queue
import subprocess
from fuzzywuzzy import process
import random
import threading
import platform
import webbrowser
import sys  # ADDED for command-line arguments
from collections import Counter
import requests
import json
from PIL import ImageDraw

import customtkinter as ctk
 
from PIL import Image, ImageTk
from customtkinter import CTkImage


from deepface import DeepFace
BASE_API_URL = "http://127.0.0.1:5000"
import pygame
import speech_recognition as sr
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
ctk.set_appearance_mode("dark")              # "light", "dark", or "system"
ctk.set_default_color_theme("dark-blue") 
# =============================
# FINAL UI COLOR SYSTEM
# =============================
# =============================================================
# THE "PERFECT LOOK" UI DESIGN CONSTANTS
# =============================================================
COLOR_BG_DARK    = "#0D0221"
COLOR_PANEL      = "#0D0221"
COLOR_CYAN_GLOW  = "#1DE9B6"
COLOR_GREEN_BTN  = "#00C853"
COLOR_TEXT_MAIN  = "#E0F2F1"
COLOR_TEXT_DIM   = "#80CBC4"

BG_MAIN = "#0F172A"
BG_PANEL = "#1B2240"

BORDER_ACCENT = "#818CF8"

ACCENT_PRIMARY = "#6366F1"
HOVER_PRIMARY = "#4F46E5"

BTN_LOCAL = "#22C55E"
BTN_SPOTIFY = "#38BDF8"

BTN_NEUTRAL = "#374151"
BTN_ACTION = "#F59E0B"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"

LANG_ACTIVE = "#22D3EE"
LANG_INACTIVE = "#EC4899"
LANG_HOVER = "#DB2777"

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except Exception:
    AudioUtilities = None
    IAudioEndpointVolume = None

# --- MONGO DB ADDED
from pymongo import MongoClient

load_dotenv()  # loads environment variables from .env

MONGO_URI = os.getenv("MONGO_URI")
history_col = None
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["emotion_music_app"]
        history_col = db["music_history"]
        print("MongoDB: connected.")
    else:
        print("MongoDB: MONGO_URI not set — DB history disabled.")
except Exception as e:
    print(f"MongoDB init error: {e}")
    history_col = None

# ---------------------------
# Configuration
# ---------------------------
CONFIG = {
    "music_mode": "Local",  # "Local" or "Spotify"
    "current_language": "english", # This will be overwritten by user's default
    "supported_languages": ["english", "malayalam", "hindi", "tamil"],

    "analysis_interval_seconds": 0.5,      # how often to run analysis (time-based)
    "detection_duration": 20,              # how long to collect detections (seconds)
    "confidence_threshold": 0.4,           # probability threshold (0.0-1.0)
    "emotions": ["angry", "happy", "neutral", "sad"],

    "face_detection_scale_factor": 1.1,
    "face_detection_min_neighbors": 5,
    "face_detection_min_size": (130, 130),
    "detection_window_max_hits": 40,       # cap for stored detections
    "camera_probe_count": 4,               # how many camera indices to cycle through

    "spotify_premium": False,
}

# ---------------------------
# App States
# ---------------------------
class AppState:
    IDLE = "IDLE"
    DETECTING = "DETECTING"
    PLAYING = "PLAYING"
    SUGGESTED = "SUGGESTED"
    CAMERA_ERROR = "CAMERA_ERROR"
    AUTH_ERROR = "AUTH_ERROR"

def create_gradient(width, height):
    img = Image.new("RGB", (width, height))
    pixels = img.load()

    for y in range(height):
        for x in range(width):
            nx = x / width
            ny = y / height
            blue = int(120 * (1 - ((nx-0.2)**2 + (ny-0.2)**2)))
            purple = int(160 * (1 - abs(nx - ny)))
            pink = int(180 * ny)

            r = min(255, 40 + pink)
            g = min(255, 60 + purple // 3)
            b = min(255, 120 + blue)

            pixels[x, y] = (r, g, b)

    return img
# ---------------------------
# Main App
# ---------------------------
class EmotionMusicPlayerApp:
    def __init__(self, root, user_email, default_language):
        self.root = root
        self.root.title("Emotion AI Music Player")
        self.root.geometry("1000x680")
        gradient_img = create_gradient(1000, 680)

        self.gradient_bg = CTkImage(
            light_image=gradient_img,
            dark_image=gradient_img,
            size=(1000, 680)
        )

        self.bg_label = ctk.CTkLabel(
            self.root,
            image=self.gradient_bg,
            text=""
        )

        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_label.lower()
        self.root.configure(fg_color=COLOR_BG_DARK)

        # -------- BACKGROUND IMAGE --------
      # # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
       # bg_path = os.path.join(BASE_DIR, "static", "assets", "bg.png")

       # self.bg_image = CTkImage(
       #     light_image=Image.open(bg_path),
       #     dark_image=Image.open(bg_path),
       #     size=(1000, 600)
       # )

        #self.bg_label = ctk.CTkLabel(
       #     self.root,
       #     image=self.bg_image,
       #     text=""
       # )

       # self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Send background behind all widgets
      #  self.bg_label.lower()


        self.user_email = user_email
        self.default_language = default_language
        print(f"App started for user: {self.user_email} with default language: {self.default_language}")

        CONFIG["current_language"] = self.default_language

        self.app_state = AppState.IDLE
        self.spotify_user_paused = False
        self.is_running = True
        self.camera_index = 1
        self.frame_counter = 0
        self.detection_start_time = None
        self._last_analysis_ts = 0.0
        self.emotion_detections = []
        self.last_detected_emotion_for_display = ""
        self.analysis_result_queue = queue.Queue()
        self.sp = None
        self.volume = None
        self.current_playlist_url = None
        self.is_paused = False
        self.song_queue = []
        self.song_history = []
        self.is_manually_skipping = False
        self.target_emotion_for_playback = ""
        self._current_filename = None
        self.full_song_list = []
        self.current_index = 0
        self.is_spotify_premium = False
        self.spotify_device_id = None
        self.spotify_monitor_thread = None
        self.is_spotify_playing = False
        self.last_logged_track_uri = None
       
        self.inquiry_pending = None            # holds 'angry' or 'sad' while waiting for user choice
        self.inquiry_start_time = None         # when inquiry began
        self.inquiry_timeout_seconds = 20  
        self.detection_paused = False    # increased from 12 → 20 for better user experience



        # --- FONTS AND GUI LAYOUT (CustomTkinter) ---
        self.title_font = ctk.CTkFont(size=20, weight="bold")
        self.label_font = ctk.CTkFont(size=13)
        self.song_font = ctk.CTkFont(size=15, weight="bold", slant="italic")
        self.status_font = ctk.CTkFont(size=11, slant="italic")
        self.placeholder_font = ctk.CTkFont(size=22, weight="bold")
        self.link_font = ctk.CTkFont(size=12, underline=True)



        # main containers

        self.webcam_frame = ctk.CTkFrame(
            self.root,
            fg_color=COLOR_PANEL,   # keep your new color
            corner_radius=0,
            width=640,
            height=480,
            border_width=3,
            border_color=COLOR_CYAN_GLOW
        )

        self.webcam_frame.place(x=20, y=20)


        self.webcam_label = ctk.CTkLabel(self.webcam_frame, text="")
        self.placeholder_label = ctk.CTkLabel(
            self.webcam_frame,
            text="Select a mode to begin.",
            font=self.placeholder_font
        )
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
        self.webcam_frame.configure(
            border_color=COLOR_CYAN_GLOW
        )

        self.controls_frame = ctk.CTkFrame(
            master=self.root,
            corner_radius=0,
            fg_color=COLOR_PANEL,   # keep your new color
            border_width=3,
            border_color=COLOR_CYAN_GLOW, # keep old subtle border so layout looks clean
            width=310,
            height=630
        )

        self.controls_frame.place(x=670, y=20)
        self.controls_frame.pack_propagate(False)

        self.controls_frame.configure(
            border_color="#818CF8"
        )


        # mode controls
        mode_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        mode_frame.pack(pady=(5, 0), padx=10)

        self.mode_label = ctk.CTkLabel(
            mode_frame,
            text=f"Mode: {CONFIG['music_mode']}",
            font=self.label_font
        )
        self.mode_label.pack()

        self.local_mode_button = ctk.CTkButton(
            mode_frame,
            text="Local",
            command=lambda: self.set_music_mode("Local"),
            width=80,
            fg_color=BTN_LOCAL,
            hover_color="#2563EB",
            text_color="white",
            corner_radius=10
        )
        self.local_mode_button.pack(side="left", padx=5)

        self.spotify_mode_button = ctk.CTkButton(
            mode_frame,
            text="Spotify",
            command=lambda: self.set_music_mode("Spotify"),
            width=80,
            fg_color=BTN_SPOTIFY,
            hover_color="#15803D",
            text_color="white",
            corner_radius=10
        )
        self.spotify_mode_button.pack(side="left", padx=5)

        # language controls
        lang_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        lang_frame.pack(pady=(5, 0), padx=10)

        self.lang_label = ctk.CTkLabel(
            lang_frame,
            text=f"Language: {CONFIG['current_language'].capitalize()}",
            font=self.label_font
        )
        self.lang_label.pack()

        self.lang_buttons = {}
        for lang in CONFIG["supported_languages"]:
            btn = ctk.CTkButton(
                lang_frame, text=lang.capitalize(),
                command=lambda l=lang: self.set_language(l),
                width=60,
                fg_color=BTN_NEUTRAL,
                hover_color="#4B5563",
                text_color="white",
                corner_radius=10
            )
            btn.pack(side="left", padx=2, pady=2)
            self.lang_buttons[lang] = btn

        self.update_mode_button_visuals()

        # status section
        ctk.CTkLabel(self.controls_frame, text="STATUS", font=self.title_font).pack(pady=(5, 10))
        ctk.CTkFrame(
            self.controls_frame,
            height=2,
            fg_color="#334155"
        ).pack(fill="x", padx=20, pady=10)
        self.emotion_label = ctk.CTkLabel(self.controls_frame, text="Detected: .", font=self.label_font)
        self.emotion_label.pack(pady=(0, 5))

        self.target_emotion_label = ctk.CTkLabel(self.controls_frame, text="Playing For: .", font=self.title_font)
        self.target_emotion_label.pack(pady=(0, 10))

        self.timer_label = ctk.CTkLabel(self.controls_frame, text="", font=self.label_font)
        self.timer_label.pack(pady=(0, 10))

        self.song_label = ctk.CTkLabel(self.controls_frame, text="None", font=self.song_font, wraplength=280)
        self.song_label.pack(pady=(5, 5))

        # clickable playlist "link" (still a label with a hand cursor)
        self.playlist_link_label = ctk.CTkLabel(self.controls_frame, text="", font=self.link_font, cursor="hand2")
        self.playlist_link_label.pack(pady=(0, 10))
        self.playlist_link_label.bind("<Button-1>", self.open_playlist_url)

        self.voice_status_label = ctk.CTkLabel(self.controls_frame, text="Voice Command: Initializing.", font=self.status_font)
        self.voice_status_label.pack(pady=(5, 0))
        self.progress_bar = ctk.CTkProgressBar(self.controls_frame, progress_color=ACCENT_PRIMARY)
        self.progress_bar.set(0) # Start it at empty
        self.progress_bar.pack(pady=10, padx=20, fill="x") 


        self.switch_cam_button = ctk.CTkButton(
            self.controls_frame,
            text="📷 Switch Camera",  # remove \u200B; font fix handles alignment
            command=self.switch_camera,
            width=180,
            fg_color=COLOR_GREEN_BTN,
            hover_color="#4F46E5",
            text_color="black",
            corner_radius=12,
            font=("Segoe UI Symbol", 14)  # same style as other buttons
        )
        self.switch_cam_button.pack(pady=5)

        # bottom buttons
        self.buttons_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.buttons_frame.pack(pady=10, padx=10, fill="x", side="bottom")
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        play_icon_path = os.path.join(BASE_DIR, "static", "assets", "play_icon.png")
        pause_icon_path = os.path.join(BASE_DIR, "static", "assets", "pause_icon.png")

        self.play_icon = CTkImage(Image.open(play_icon_path))
        self.pause_icon = CTkImage(Image.open(pause_icon_path))

         

        self.previous_button = ctk.CTkButton(
            self.buttons_frame,
            text="⏮ Previous",
            command=self.play_previous_song,
            width=180,
            fg_color=BTN_NEUTRAL,
            hover_color="#4B5563",
            border_width=1,
            border_color="#334155",
            text_color="white",
            corner_radius=12
        )
        self.previous_button.pack(pady=5)


        

        self.play_pause_button = ctk.CTkButton(
            self.buttons_frame,
            text="⏯",
            image=self.pause_icon,
            command=self.toggle_pause_play,
            width=180,
            fg_color=ACCENT_PRIMARY,
            hover_color="#4F46E5",
            border_width=1,
            border_color="#334155",
            text_color="white",
            corner_radius=12
        )
        self.play_pause_button.pack(pady=5)


        

        self.next_button = ctk.CTkButton(
            self.buttons_frame,
            text="Next ⏭",
            command=self.play_next_song,
            width=180,
            fg_color=BTN_ACTION,
            hover_color="#D97706",
            border_width=1,
            border_color="#334155",
            text_color="white",
            corner_radius=12
        )
        self.next_button.pack(pady=5)  

        # Setup
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.initialize_system_components()
        self.initialize_camera()

        # Start voice thread
        self.voice_thread = threading.Thread(target=self.listen_for_voice_commands, daemon=True)
        self.voice_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update()

        # Key bindings
        self.root.bind("<space>", lambda e: self.toggle_pause_play())
        self.root.bind("<Right>", lambda e: self.play_next_song())
        self.root.bind("<Left>", lambda e: self.play_previous_song())
        self.root.bind("c", lambda e: self.start_detection())
        self.progress_bar.pack_forget()

    # ---------------------------
    # --- MODIFIED: Database Methods Integrated into the Class ---
    # ---------------------------
    def _show_search_status(self, text):
        self.webcam_label.place_forget()
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
        self.placeholder_label.configure(text=text)

    def _display_free_user_link(self, playlist):
        """Configures the UI for a non-premium user."""
        self.webcam_label.place_forget()
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
        self.placeholder_label.configure(text="Playlist Suggested!\nSay 'camera on' to detect again.")
        
        self.current_playlist_url = playlist.get("external_urls", {}).get("spotify")
        self.playlist_link_label.configure(text="Click to open in Spotify")
        self.play_pause_button.configure(state="disabled")
        self.next_button.configure(state="disabled")
        self.previous_button.configure(state="disabled")

    def _start_premium_playback(self, playlist):
        """
        Handles Premium playback.
        Resume from last unfinished song ONLY if same playlist.
        Does NOT affect non-premium users.
        """
        # 🔐 Extra safety
        if not self.is_spotify_premium:
            return

        self._find_active_spotify_device()
            
        if not self.spotify_device_id:
            self.song_label.configure(text="No active Spotify device!")
            self.placeholder_label.configure(text="Open Spotify on your device first.")
            self.webcam_label.place_forget()
            self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
            return

        playlist_uri = playlist['uri']
        playlist_id = playlist['id']
        print(f"Playing {playlist['name']} on {self.spotify_device_id}")

        # 🔁 RESET TRACK CACHE (important)
        self.last_logged_track_uri = None

        try:
            # 1. STOP DETECTION IMMEDIATELY
            self.app_state = AppState.PLAYING 
            self.webcam_label.place_forget()
            self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
            self.placeholder_label.configure(text=f"Playing: {playlist['name']}...")

            # 2. Force Wake Up
            try:
                self.sp.transfer_playback(
                    device_id=self.spotify_device_id,
                    force_play=True
                )
            except:
                pass

            time.sleep(0.5)

            # ===========================
            # 🔁 NEW: RESUME LOGIC (SAFE)
            # ===========================
            resume_state = self._get_spotify_state(playlist_id)

            if resume_state and resume_state.get("track_uri"):
                print("▶️ Resuming Spotify from last track:", resume_state["track_uri"])
                self.sp.start_playback(
                    device_id=self.spotify_device_id,
                    context_uri=playlist_uri,
                    offset={"uri": resume_state["track_uri"]}
                )
            else:
                print("▶️ Starting Spotify playlist from beginning")
                self.sp.start_playback(
                    device_id=self.spotify_device_id,
                    context_uri=playlist_uri
                )

            # 3. SAVE HISTORY (UNCHANGED)
            self.save_history_log(
                log_type="spotify",
                language=CONFIG["current_language"],
                emotion=self.target_emotion_for_playback,
                name=playlist["name"],
                is_track=False
            )

            self.is_spotify_playing = True

            # 4. Update Buttons (UNCHANGED)
            self.playlist_link_label.configure(text="")
            self.play_pause_button.configure(state="normal", image=self.pause_icon)
            self.next_button.configure(state="normal")
            self.previous_button.configure(state="normal")

            # 5. Start Monitor (UNCHANGED)
            if self.spotify_monitor_thread and self.spotify_monitor_thread.is_alive():
                self.is_running_monitor = False
                time.sleep(0.5)

            self.is_running_monitor = True
            self.spotify_monitor_thread = threading.Thread(
                target=self._spotify_playback_monitor,
                args=(playlist_id,),
                daemon=True
            )
            self.spotify_monitor_thread.start()

        except spotipy.exceptions.SpotifyException as e:
            print(f"Spotify Playback Error: {e}")
            if "premium" in str(e).lower():
                self.is_spotify_premium = False
                self._display_free_user_link(playlist)
            else:
                self.song_label.configure(text="Spotify Error: Open App & Retry")



    def _find_active_spotify_device(self):
        if not self.sp:
            return

        try:
            devices = self.sp.devices().get("devices", [])

            if not devices:
                self.spotify_device_id = None
                return

            # Prefer active device
            for d in devices:
                if d["is_active"]:
                    self.spotify_device_id = d["id"]
                    return

            # If none active, FORCE activate first device
            self.spotify_device_id = devices[0]["id"]
            self.sp.transfer_playback(
                device_id=self.spotify_device_id,
                force_play=True
            )
            time.sleep(1)

        except Exception as e:
            print("Spotify device error:", e)
            self.spotify_device_id = None


    def _spotify_playback_monitor(self, playlist_id):
        time.sleep(3)  # grace period
        was_playing = False

        while self.is_running_monitor and self.is_running:
            try:
                playback = self.sp.current_playback()

                # ---- MUSIC PLAYING ----
                if playback and playback.get("is_playing"):
                    was_playing = True
                    self.spotify_user_paused = False
                    self.is_spotify_playing = True

                    track = playback.get("item")
                    if track:
                        name = track["name"]
                        artist = track["artists"][0]["name"]

                        # ✅ UPDATE UI
                        self.root.after(
                            0,
                            lambda n=name, a=artist: self.song_label.configure(
                                text=f"{n}\nby {a}"
                            )
                        )

                        # ✅ SAVE RESUME STATE (SONG ONLY)
                        track_uri = track.get("uri")

                        if track_uri and track_uri != self.last_logged_track_uri:
                            self.last_logged_track_uri = track_uri
                            self._log_spotify_state(
                                playlist_id=playlist_id,
                                track_uri=track_uri,
                                progress_ms=0  # not used
                            )

                # ---- MUSIC PAUSED (USER ACTION) ----
                elif playback and not playback.get("is_playing") and playback.get("context"):
                    self.spotify_user_paused = True
                    self.is_spotify_playing = False

                # ---- PLAYLIST FINISHED ----
                elif playback and not playback.get("is_playing") and playback.get("context") is None and was_playing:
                    print("Spotify playlist fully finished.")
                    self.is_spotify_playing = False
                    self.is_running_monitor = False
                    break

                time.sleep(3)

            except Exception as e:
                print("Spotify monitor error:", e)
                break




    def get_last_song_index(self, language, emotion):
        """Return last stored index for language+emotion, default 0."""
        if not self.user_email or history_col is None:
            return 0
        try:
            # Find a record for this specific user
            doc = history_col.find_one({"user_email": self.user_email, "type": "local_resume", "language": language, "emotion": emotion})
            if doc:
                return doc.get("last_song_index", 0) or 0
        except Exception as e:
            print(f"get_last_song_index error: {e}")
        return 0

    def update_last_song_index(self, language, emotion, index, song_name):
        """Update DB with last index + song name for RESUMING playback."""
        if not self.user_email or history_col is None:
            return
        try:
            # This record is just for resuming, identified by a special type
            history_col.update_one(
                {"user_email": self.user_email, "type": "local_resume", "language": language, "emotion": emotion},
                {"$set": {"last_song_index": index, "last_song_name": os.path.splitext(song_name)[0]}},
                upsert=True
            )
        except Exception as e:
            print(f"update_last_song_index error: {e}")
    
    def save_history_log(self, log_type, language, emotion, name, is_track=False):
        """Saves a record of a played song or playlist to the history log."""
        if not self.user_email or history_col is None:
            return
        
        record = {
            "user_email": self.user_email,
            "language": language,
            "emotion": emotion,
            "detection_mode": "camera" # Or you could pass this in as a parameter
        }

        if log_type == "local":
            record["type"] = "local_play"
            record["song_name"] = os.path.splitext(name)[0]
        elif log_type == "spotify":
            record["type"] = "spotify_play"
            # NEW: Differentiate between a track and a playlist
            if is_track:
                record["song_name"] = name
                record["playlist_name"] = None # Explicitly set playlist to null for tracks
            else:
                record["playlist_name"] = name
                record["song_name"] = None
        
        try:
            history_col.insert_one(record)
            print(f"History log saved for {name}")
        except Exception as e:
            print(f"save_history_log error: {e}")

    # --- NEW: API helpers for Spotify state ---
    def _get_spotify_state(self, playlist_id):
        if not self.is_spotify_premium:
            return None

        try:
            url = f"{BASE_API_URL}/get_spotify_state/{playlist_id}"
            response = requests.get(
                url,
                params={"user_email": self.user_email},  # ✅ REQUIRED
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                return data if data else None

        except Exception as e:
            print(f"Error fetching Spotify state: {e}")

        return None


    def _log_spotify_state(self, playlist_id, track_uri, progress_ms):
        print("🔥 _log_spotify_state CALLED", playlist_id, track_uri)

        if not self.is_spotify_premium:
            return

        try:
            url = f"{BASE_API_URL}/log_spotify_state"
            payload = {
                "user_email": self.user_email,   # ✅ THIS WAS MISSING
                "playlist_id": playlist_id,
                "track_uri": track_uri,
                "progress_ms": progress_ms
            }

            r = requests.post(url, json=payload, timeout=5)
            print("📡 Spotify state API response:", r.status_code, r.text)

        except Exception as e:
            print(f"❌ Error logging Spotify state: {e}")
    

    # ---------------------------
    # Initialization helpers
    # ---------------------------
    def initialize_system_components(self):
        """Initializes pygame mixer and system volume control (platform-aware)."""
        try:
            pygame.mixer.init()
        except pygame.error as e:
            print(f"Error initializing pygame mixer: {e}")

        try:
            if platform.system() == "Windows" and AudioUtilities and IAudioEndpointVolume:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                self.volume = None
        except Exception as e:
            print(f"Could not initialize system volume control: {e}")
            self.volume = None

    def speak_native(self, text):
        """Uses the OS's native TTS engine for reliable, non-blocking speech."""
        print(f"[TTS] Speaking natively: {text}")
        system = platform.system()
        try:
            if system == "Windows":
                # PowerShell command is robust and doesn't open a window
                command = f'powershell -Command "Add-Type –AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{text}\');"'
                subprocess.run(command, check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif system == "Darwin": # macOS
                os.system(f'say "{text}"')
            else: # Linux
                os.system(f'espeak "{text}"')
        except Exception as e:
            print(f"Native TTS failed: {e}")


    def speak_blocking(self, text):
        """Queues text to be spoken by the OS's native TTS in a background thread."""
        threading.Thread(target=self.speak_native, args=(text,), daemon=True).start()

        

    def update_mode_button_visuals(self):
        """UI visuals for active mode and language (CustomTkinter)."""
        if CONFIG["music_mode"] == "Local":
            self.local_mode_button.configure(fg_color="#14CA63")
            self.spotify_mode_button.configure(fg_color="#1EA4F2")
        else:
            self.local_mode_button.configure(fg_color="#15F476")
            self.spotify_mode_button.configure(fg_color="#194ADF")

        for lang, btn in self.lang_buttons.items():
            if lang == CONFIG["current_language"]:
                btn.configure(fg_color="#19DCDC")
            else:
                btn.configure(fg_color="#EE08B9")



    # ---------------------------
    # Camera & display
    # ---------------------------
    def initialize_camera(self):
        """Tries multiple backends to open camera robustly."""
        if hasattr(self, 'cap') and self.cap and self.cap.isOpened():
            try:
                self.cap.release()
            except Exception:
                pass
        opened = False
        for i in range(CONFIG["camera_probe_count"]):
            idx = (self.camera_index + i) % CONFIG["camera_probe_count"]
            for api in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
                try:
                    cap = cv2.VideoCapture(idx, api)
                except Exception:
                    cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    self.camera_index = idx
                    self.cap = cap
                    opened = True
                    break
            if opened:
                break
        if not opened:
            self.app_state = AppState.CAMERA_ERROR
            self.placeholder_label.configure(text=f"Error: Camera {self.camera_index} not found.")
        else:
            print(f"Camera opened at index {self.camera_index}")

    def switch_camera(self):
        """Cycle to next camera index modulo probe count."""
        self.camera_index = (self.camera_index + 1) % CONFIG["camera_probe_count"]
        if hasattr(self, 'cap') and getattr(self, 'cap', None):
            try:
                if self.cap.isOpened():
                    self.cap.release()
            except Exception:
                pass
        self.initialize_camera()
        if self.app_state != AppState.CAMERA_ERROR:
            self.start_detection()

    def display_frame(self, frame):
        """Display frame with overlay of detected emotion label."""
        try:
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        except Exception:
            return
        faces = self.face_cascade.detectMultiScale(
            gray_frame,
            scaleFactor=CONFIG["face_detection_scale_factor"],
            minNeighbors=CONFIG["face_detection_min_neighbors"],
            minSize=CONFIG["face_detection_min_size"]
        )
        if len(faces) > 0:
            (x, y, w, h) = faces[0]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            if self.last_detected_emotion_for_display:
                cv2.putText(frame, self.last_detected_emotion_for_display.capitalize(), (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        img = Image.fromarray(cv2image)
        imgtk = ImageTk.PhotoImage(image=img)
        self.webcam_label.imgtk = imgtk
        self.webcam_label.configure(image=imgtk)

    # ---------------------------
    # Emotion detection helpers
    # ---------------------------
    def _largest_face_roi(self, frame_gray):
        faces = self.face_cascade.detectMultiScale(
            frame_gray,
            scaleFactor=CONFIG["face_detection_scale_factor"],
            minNeighbors=CONFIG["face_detection_min_neighbors"],
            minSize=CONFIG["face_detection_min_size"]
        )
        if len(faces) == 0:
            return None
        return max(faces, key=lambda f: f[2] * f[3])

    def run_emotion_analysis(self, frame):
        """Analyze (in separate thread)."""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            roi = self._largest_face_roi(gray)
            if roi is not None:
                x, y, w, h = roi
                face_frame = frame[y:y+h, x:x+w]
            else:
                face_frame = frame
            try:
                analysis = DeepFace.analyze(face_frame, actions=['emotion'], enforce_detection=False, detector_backend='mtcnn')
            except Exception:
                analysis = DeepFace.analyze(face_frame, actions=['emotion'], enforce_detection=False)
            if isinstance(analysis, list) and len(analysis) > 0:
                analysis = analysis[0]
            emotions_dict = analysis.get('emotion') or {}
            if emotions_dict:
                label, prob = max(emotions_dict.items(), key=lambda kv: kv[1])
                if label in CONFIG["emotions"] and prob >= (CONFIG["confidence_threshold"] * 100.0):
                    self.analysis_result_queue.put(label)
                    return
                dom = analysis.get('dominant_emotion')
                if dom in CONFIG["emotions"]:
                    self.analysis_result_queue.put(dom)
                    return
            else:
                dom = analysis.get('dominant_emotion')
                if dom in CONFIG["emotions"]:
                    self.analysis_result_queue.put(dom)
        except Exception as e:
            print(f"Emotion analysis error: {e}")

    def process_analysis_queue(self):
        """Move items from worker queue to app state."""
        if getattr(self, "detection_paused", False):
         return
        try:
            while not self.analysis_result_queue.empty():
                detected_emotion = self.analysis_result_queue.get_nowait()
                self.emotion_detections.append(detected_emotion)
                if len(self.emotion_detections) > CONFIG["detection_window_max_hits"]:
                    self.emotion_detections = self.emotion_detections[-CONFIG["detection_window_max_hits"]:]
                self.last_detected_emotion_for_display = detected_emotion
                self.root.after(0, lambda e=detected_emotion: self.emotion_label.configure(text=f"Detected: {e.capitalize()}"))
        except queue.Empty:
            pass

    def get_confident_emotion(self):
        """Return most frequent detection, with special sensitivity for 'sad'."""
        if not self.emotion_detections:
            return "neutral"

        emotion_counts = Counter(self.emotion_detections)
        most_common, count = emotion_counts.most_common(1)[0]

        total_detections = len(self.emotion_detections)
        confidence_percentage = count / total_detections

        if most_common == 'sad' and confidence_percentage >= 0.25:
            print(f"Confident emotion found (sensitive rule): {most_common} ({confidence_percentage:.0%})")
            return most_common
        elif confidence_percentage >= 0.4:
            print(f"Confident emotion found (standard rule): {most_common} ({confidence_percentage:.0%})")
            return most_common
        else:
            print(f"No confident emotion found (Top was {most_common} at {confidence_percentage:.0%}). Defaulting to neutral.")
            return "neutral"

    # ---------------------------
    # Detection lifecycle
    # ---------------------------
    def start_detection(self):
        """Reset and start detection if not in error states."""
        self.inquiry_pending = None
        self.inquiry_start_time = None
        self.last_locked_emotion = None
        if self.app_state in [AppState.CAMERA_ERROR, AppState.AUTH_ERROR]:
            return
        self.inquiry_pending = None
        self.inquiry_start_time = None
        self.detection_paused = False
        self.last_locked_emotion = None

        self.placeholder_label.place_forget()
        self.webcam_label.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)
        self.progress_bar.pack(pady=10, padx=20, fill="x") # Show the bar
        self.current_playlist_url = None
        self.playlist_link_label.configure(text="")
        self.play_pause_button.configure(state="normal")
        self.next_button.configure(state="normal")
        self.previous_button.configure(state="normal")

        if CONFIG["music_mode"] == "Local" and pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self.detection_start_time = None
        self.emotion_detections.clear()
        self._last_analysis_ts = 0.0
        self.app_state = AppState.DETECTING
        self.song_label.configure(text="None")
        self.emotion_label.configure(text="Detected: Detecting...")
        self.target_emotion_label.configure(text="Playing For: ...")
        self.last_detected_emotion_for_display = ""
        self._current_filename = None

    def handle_detection_timing(self):
        """Time-based analysis cadence; locks in once duration reached."""
        if getattr(self, "detection_paused", False):
         return
        if self.detection_start_time is None:
            self.detection_start_time = time.time()
            self._last_analysis_ts = 0.0
        time_elapsed = time.time() - self.detection_start_time
        time_left = max(0, CONFIG["detection_duration"] - time_elapsed)
        self.timer_label.configure(text=f"Detecting for: {int(time_left)}s")
        # Update the progress bar
        progress = time_elapsed / CONFIG["detection_duration"]
        self.progress_bar.set(progress)
        if time.time() - getattr(self, "_last_analysis_ts", 0.0) >= CONFIG["analysis_interval_seconds"]:
            ret, frame = self.cap.read()
            if ret:
                threading.Thread(target=self.run_emotion_analysis, args=(frame.copy(),), daemon=True).start()
                self._last_analysis_ts = time.time()
        if time_elapsed >= CONFIG["detection_duration"]:
            chosen = self.get_confident_emotion()
            if not self.emotion_detections:
                chosen = "neutral"
                self.emotion_label.configure(text="Detected: No face - defaulting to Neutral")
            self.lock_in_emotion(chosen)

    def lock_in_emotion(self, emotion):

        if getattr(self, "last_locked_emotion", None) == emotion:
            print(f"Already locked emotion '{emotion}' — skipping duplicate lock.")
            return
        self.last_locked_emotion = emotion

         
        if self.app_state != AppState.DETECTING:
            return
        self.progress_bar.set(0)  # Reset the bar
        self.progress_bar.pack_forget()  # Hide the bar again

        self.target_emotion_for_playback = emotion
        print(f"Emotion locked in: {emotion}. Finding matching music.")
        self.target_emotion_label.configure(text=f"Playing For: {self.target_emotion_for_playback.capitalize()}")

        if emotion in ["angry", "sad"]:
            # set inquiry state
            self.inquiry_pending = emotion
            self.inquiry_start_time = time.time()
            self.detection_paused = True
            print(f"Inquiry started for '{emotion}'. Detection paused.")


            # reset detection timer so next detection starts fresh after resume
            self.detection_start_time = None
            # optional: clear any queued analysis results to avoid backlog
            try:
                while not self.analysis_result_queue.empty():
                    self.analysis_result_queue.get_nowait()
            except Exception:
                pass

            self.webcam_label.place_forget()  
            self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
            self.placeholder_label.configure(text=f"Detected '{emotion}'. Say 'same mood' to vent, or 'change mood' to calm down.")

            self.speak_blocking(f"Feeling {emotion}. Say same mood to vent, or change mood to calm down.")

            return

        if CONFIG["music_mode"] == "Spotify":
            # ✅ UI first
            self.webcam_label.place_forget()
            self.progress_bar.pack_forget()
            self._show_search_status("Searching Spotify playlist...")

            # ✅ run Spotify search in background
            threading.Thread(
                target=self.suggest_spotify_playlist,
                daemon=True
            ).start()
        else:
            self.play_local_music()



    # ---------------------------
    # Spotify helpers
    # ---------------------------
    
    def is_spotify_token_valid(self):
        if not hasattr(self, 'spotify_expires_at'):
            return False
        return time.time() < self.spotify_expires_at

    # In main.py
    def authenticate_spotify(self):
        """Authenticate Spotify using ONLY the token provided from app.py."""
        try:
            if self.spotify_access_token and self.is_spotify_token_valid():
                self.sp = spotipy.Spotify(auth=self.spotify_access_token)
                self.sp.current_user()  # This API call is now safe to make.
                
                print("Spotify authenticated using token from web session.")
                self.app_state = AppState.IDLE
                self.placeholder_label.configure(text="Spotify connected successfully!")
            else:
                print("Spotify token is missing or invalid. Setting AUTH_ERROR.")
                self.placeholder_label.configure(text="Spotify not connected.\nPlease link your account on the web dashboard.")
                self.app_state = AppState.AUTH_ERROR
                self.sp = None

        except Exception as e:
            print(f"Spotify auth error (API call failed): {e}")
            self.placeholder_label.configure(text="Spotify Auth Error.\nPlease re-link on the dashboard.")
            self.app_state = AppState.AUTH_ERROR
            self.sp = None


    def suggest_spotify_playlist(self):
        """
        Finds the most popular playlist matching language and emotion, with a fallback.
        """
        if not self.sp:
            self.song_label.configure(text="Spotify not authenticated.")
            return

        self.app_state = AppState.SUGGESTED

        self.song_label.configure(text="Searching for the perfect playlist...")
         
        self.timer_label.configure(text="")

        self._show_search_status("Searching Spotify playlist...")
        
        LANGUAGE_SYNONYMS = {
            "english": ["english", "hollywood"],
            "hindi": ["hindi", "bollywood"],
            "malayalam": ["malayalam", "mollywood"],
            "tamil": ["tamil", "kollywood"],
        }
        EMOTION_SYNONYMS = {
            "happy": ["happy", "joy", "positive", "vibe", "energetic"],
            "sad": ["sad", "melancholy", "blue", "poignant"],
            "angry": ["angry", "rage", "furious", "aggressive"],
            "neutral": ["neutral", "calm", "chill", "serene"],
        }

        lang = CONFIG["current_language"].lower()
        emo = self.target_emotion_for_playback.lower()
        lang_keywords = LANGUAGE_SYNONYMS.get(lang, [lang])
        emo_keywords = EMOTION_SYNONYMS.get(emo, [emo])

        try:
            query_templates = [ f"{lang} {emo}", f"{emo} {lang}", f"{lang} {emo} playlist", f"{emo} vibes" ]
            seen_ids = set()
            print(f"🔎 Dynamically searching Spotify for a {lang} {emo} playlist...")
            for q in query_templates:
                results = self.sp.search(q=q, type="playlist", limit=15)
                items = results.get('playlists', {}).get('items', []) or []
                for p in items:
                    if p and p.get('id'):
                        seen_ids.add(p['id'])
            
            valid_candidates = []
            if seen_ids:
                print(f"Found {len(seen_ids)} potential playlists. Fetching details...")
                for pid in list(seen_ids):
                    try:
                        playlist_details = self.sp.playlist(pid, fields="name,description,followers,external_urls,id,uri")
                        text_to_check = (playlist_details.get('name', '') + " " + playlist_details.get('description', '')).lower()
                        if any(k in text_to_check for k in lang_keywords) and any(k in text_to_check for k in emo_keywords):
                            valid_candidates.append(playlist_details)
                    except Exception:
                        pass
            
            chosen_playlist = None
            if valid_candidates:
                print(f"Found {len(valid_candidates)} relevant playlists. Selecting the most popular.")
                chosen_playlist = max(valid_candidates, key=lambda p: p.get('followers', {}).get('total', 0))
            
            # --- NEW: Fallback search if the primary search finds no valid candidates ---
            if not chosen_playlist:
                print("Primary search failed. Trying fallback search...")
                results = self.sp.search(q=f"{emo} playlist", type="playlist", limit=1)
                items = results.get('playlists', {}).get('items', []) or []
                if items:
                    pid = items[0]['id']
                    chosen_playlist = self.sp.playlist(pid, fields="name,description,followers,external_urls,id,uri")
            # --- END OF FALLBACK ---

            if chosen_playlist:
                playlist_name = chosen_playlist.get("name", "Playlist")
                self.song_label.configure(text=playlist_name)
                followers = chosen_playlist.get('followers', {}).get('total', 0)
                print(f"🎶 Selected playlist: {playlist_name} ({followers} followers)")

                if self.is_spotify_premium:
                    self._start_premium_playback(chosen_playlist)
                else:
                    self.save_history_log("spotify", lang, emo, playlist_name)
                    self._display_free_user_link(chosen_playlist)
            else:
                self.song_label.configure(text=f"No relevant playlist found for '{lang} {emo}'.")

        except Exception as e:
            print(f"Error getting Spotify playlist: {e}")
            self.song_label.configure(text="Spotify Search Error")

    # ---------------------------
    # Local music playback (pygame)
    # ---------------------------
    def play_local_music(self):
        """Pick MP3s from static/music/<language>/<emotion> and play sequentially."""
        self.app_state = AppState.PLAYING
        self.timer_label.configure(text="")
        self.webcam_label.place_forget() 
        self.placeholder_label.configure(text="Playing Music...\nSay 'camera on' to detect again.")
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
        emotion_folder = os.path.join("static", "music", CONFIG["current_language"], self.target_emotion_for_playback)
        song_files = []
        if os.path.isdir(emotion_folder):
            song_files = [f for f in os.listdir(emotion_folder) if f.lower().endswith('.mp3')]
        if not song_files and CONFIG["current_language"] != "english":
            self.song_label.configure(text=f"No songs in {CONFIG['current_language']}. Falling back to English.")
            emotion_folder = os.path.join("static", "music", "english", self.target_emotion_for_playback)
            if os.path.isdir(emotion_folder):
                song_files = [f for f in os.listdir(emotion_folder) if f.lower().endswith('.mp3')]

        if not song_files:
            self.song_label.configure(text=f"No songs found for this mood.")
            return

        song_files.sort()
        self.full_song_list = song_files
        try:
            last_index = self.get_last_song_index(CONFIG["current_language"], self.target_emotion_for_playback)
            last_index = int(last_index) if isinstance(last_index, (int, float)) else 0
            if last_index < 0 or last_index >= len(self.full_song_list):
                last_index = 0
        except Exception:
            last_index = 0
        self.current_index = last_index
        self.song_history = []
        self.play_song_at_index(self.current_index)

    def play_song_at_index(self, index):
        """Play a song given its absolute index in full_song_list and update DB."""
        if not self.full_song_list:
            return
        try:
            index = int(index) % len(self.full_song_list)
        except Exception:
            index = 0
        song_name = self.full_song_list[index]
        song_path = os.path.join("static", "music", CONFIG["current_language"], self.target_emotion_for_playback, song_name)
        try:
            pygame.mixer.music.load(song_path)
            pygame.mixer.music.play()
            self._current_filename = song_name
            self.song_label.configure(text=os.path.splitext(song_name)[0])
            self.is_paused = False
            self.play_pause_button.configure(image=self.pause_icon, text="Pause")
            self.current_index = index
            
            # --- MODIFIED: Update resume point AND save to history log ---
            self.update_last_song_index(CONFIG["current_language"], self.target_emotion_for_playback, index, song_name)
            self.save_history_log("local", CONFIG["current_language"], self.target_emotion_for_playback, song_name)

        except Exception as e:
            print(f"Error playing file at index {index}: {e}")
            self.song_label.configure(text="Error playing file.")

    def play_next_song_from_queue(self):
        """Advances to next song in the full list."""
        if not self.full_song_list:
            self.play_local_music()
            return
        try:
            next_index = (self.current_index + 1) % len(self.full_song_list)
            if pygame.mixer.get_init() and (pygame.mixer.music.get_busy() or self.is_paused):
                if getattr(self, "_current_filename", None):
                    self.song_history.append(self._current_filename)
            self.play_song_at_index(next_index)
        except Exception as e:
            print(f"play_next_song_from_queue error: {e}")

    def play_next_song(self):
        """Manual next button handler for both Local and Spotify."""
        if CONFIG["music_mode"] == "Spotify" and self.is_spotify_premium:
            if self.sp and self.spotify_device_id:
                try:
                    self.sp.next_track(device_id=self.spotify_device_id)

                    # ✅ FORCE UI + STATE SYNC
                    self.is_spotify_playing = True
                    self.play_pause_button.configure(
                        image=self.pause_icon,
                        text="Pause"
                    )

                except Exception as e:
                    print(f"Spotify next error: {e}")

        elif CONFIG["music_mode"] == "Local" and self.app_state == AppState.PLAYING:
            self.is_manually_skipping = True
            self.play_next_song_from_queue()


    def play_previous_song(self):
        """Manual previous button handler for both Local and Spotify."""
        if CONFIG["music_mode"] == "Spotify" and self.is_spotify_premium:
            if self.sp and self.spotify_device_id:
                try:
                    self.sp.previous_track(device_id=self.spotify_device_id)

                    # ✅ FORCE UI + STATE SYNC
                    self.is_spotify_playing = True
                    self.play_pause_button.configure(
                        image=self.pause_icon,
                        text="Pause"
                    )

                except Exception as e:
                    print(f"Spotify previous error: {e}")

        elif CONFIG["music_mode"] == "Local" and self.app_state == AppState.PLAYING:
            self.is_manually_skipping = True
            try:
                if self.song_history:
                    previous_song_name = self.song_history.pop()
                    try:
                        idx = self.full_song_list.index(previous_song_name)
                    except ValueError:
                        idx = None
                    if idx is not None:
                        self.play_song_at_index(idx)

                        # ✅ LOCAL UI SYNC
                        self.is_paused = False
                        self.play_pause_button.configure(
                            image=self.pause_icon,
                            text="Pause"
                        )
                        return

                prev_index = (self.current_index - 1) % len(self.full_song_list)
                self.play_song_at_index(prev_index)

                # ✅ LOCAL UI SYNC
                self.is_paused = False
                self.play_pause_button.configure(
                    image=self.pause_icon,
                    text="Pause"
                )

            except Exception as e:
                self.song_label.configure(text="Error playing file.")
                print(f"Error playing previous: {e}")

 

    def toggle_pause_play(self):
        """Pause/unpause for both Local and Spotify playback."""
        if CONFIG["music_mode"] == "Spotify" and self.is_spotify_premium:
            if self.sp and self.spotify_device_id:
                try:
                    if self.is_spotify_playing:
                        self.sp.pause_playback(device_id=self.spotify_device_id)
                        self.is_spotify_playing = False
                        self.play_pause_button.configure(image=self.play_icon, text="Play")
                    else:
                        self.sp.start_playback(device_id=self.spotify_device_id)
                        self.is_spotify_playing = True
                        self.play_pause_button.configure(image=self.pause_icon, text="Pause")
                except Exception as e:
                    print(f"Spotify toggle pause/play error: {e}")

        elif CONFIG["music_mode"] == "Local":
            if self.is_paused:
                try:
                    pygame.mixer.music.unpause()
                    self.is_paused = False
                    self.play_pause_button.configure(image=self.pause_icon, text="Pause")
                except Exception: pass
            else:
                try:
                    pygame.mixer.music.pause()
                    self.is_paused = True
                    self.play_pause_button.configure(image=self.play_icon, text="Play")
                except Exception: pass

    def check_local_music_end(self):
        """Called frequently from main loop to detect when song finished."""
        try:
            if (CONFIG["music_mode"] == "Local" and
            self.app_state == AppState.PLAYING and
            pygame.mixer.get_init() and
            not pygame.mixer.music.get_busy() and
            not self.is_paused and
            not self.is_manually_skipping and
            not getattr(self, "detection_paused", False)):
                print("Song finished, starting new detection.")
                self.start_detection()

        except Exception as e:
            print(f"check_local_music_end error: {e}")

    # ---------------------------
    # Volume control
    # ---------------------------
    def change_system_volume(self, delta):
        """Adjust system master volume (Windows via pycaw)."""
        if self.volume is None:
            print("System volume control is not available on this platform.")
            return
        try:
            current_volume = self.volume.GetMasterVolumeLevelScalar()
            new_volume = max(0.0, min(1.0, current_volume + delta))
            self.volume.SetMasterVolumeLevelScalar(new_volume, None)
            print(f"System volume changed to {int(new_volume * 100)}%")
        except Exception as e:
            print(f"Failed to change system volume: {e}")

    # ---------------------------
    # Voice recognition
    # ---------------------------
    def listen_for_voice_commands(self):
        """Improved voice loop:
        - longer noise calibration (duration=2)
        - phrase_time_limit increased (6s)
        - timeout reduced (3s)
        - GUI label shows the recognized phrase
        - uses speak_blocking everywhere (no direct runAndWait)
        - slightly lower fuzzy threshold for better recognition
        """
        actions = [
            "camera on", "start camera", "begin detection",
            "volume up", "increase volume", "louder",
            "volume down", "decrease volume", "softer",
            "pause", "pause music", "stop", "stop music",
            "play", "resume", "start music",
            "next song", "next", "skip",
            "previous song", "previous", "go back",
            "what song"
        ]

        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        r.energy_threshold = 300
        r.pause_threshold = 0.6

        mic = None
        try:
            mic = sr.Microphone()
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=2)
            self.root.after(0, lambda: self.voice_status_label.configure(text="Voice Command: Ready"))
        except Exception:
            self.root.after(0, lambda: self.voice_status_label.configure(text="Voice Command: Mic Error"))
            return

        while self.is_running:
            try:
                with sr.Microphone() as source:
                    # Update UI
                    self.root.after(0, lambda: self.voice_status_label.configure(text="Voice Command: Listening..."))
                    audio = r.listen(source, timeout=3, phrase_time_limit=6)


                try:
                    command = r.recognize_google(audio).lower()
                    print(f"Voice command heard: '{command}'")
                    self.root.after(0, lambda cmd=command: self.update_voice_status(f"Heard: '{cmd}'", hold_ms=2500))
                    time.sleep(2.0)

                except sr.UnknownValueError:
                    self.root.after(0, lambda: self.voice_status_label.configure(text="Voice Command: Didn't catch that"))
                    continue
                except sr.RequestError as e:
                    print(f"Google API request error: {e}")
                    self.root.after(0, lambda: self.voice_status_label.configure(text="Voice Command: API Error"))
                    continue

                language_changed = False
                for lang in CONFIG["supported_languages"]:
                    if lang in command:
                        self.root.after(0, lambda l=lang: self.set_language(l))
                        #self.speak_blocking(f"Language set to {lang}")
                        language_changed = True
                        break
                if language_changed:
                    continue

                # Inquiry handling (same mood / change mood)
                if self.inquiry_pending:
                    INQUIRY_SYNONYMS = {
                        "same": ["same mood", "same", "vent", "venting", "keep same"],
                        "change": ["change mood", "change", "calm", "calm down", "help me calm"]
                    }
                    flat = []
                    map_to_action = {}
                    for k, lst in INQUIRY_SYNONYMS.items():
                        for p in lst:
                            flat.append(p)
                            map_to_action[p] = k

                    best_inq, score_inq = process.extractOne(command, flat)
                    if score_inq >= 65:
                        action = map_to_action.get(best_inq, None)
                        chosen = self.inquiry_pending if action == "same" else "neutral"
                        pending = self.inquiry_pending
                        self.inquiry_pending = None
                        self.inquiry_start_time = None

                        # Update UI and speak
                        self.target_emotion_for_playback = chosen
                        self.target_emotion_label.configure(text=f"Playing For: {self.target_emotion_for_playback.capitalize()}")
                        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
                        if action == "same":
                            self.speak_blocking("Okay")
                        else:
                            self.speak_blocking("Okay")

                        # Play music
                        if CONFIG["music_mode"] == "Spotify":
                            self.suggest_spotify_playlist()
                        else:
                            self.play_local_music()

                        continue
                    else:
                        # not confident enough for inquiry response
                        self.root.after(0, lambda: self.voice_status_label.configure(text="Voice Command: Waiting for reply..."))
                        continue

                # Normal commands — fuzzy match
                best_match, score = process.extractOne(command, actions)
                # lower threshold slightly so we catch more variants (was 80)
                if score < 70:
                    print(f"Command '{command}' not confident enough (Best match: {best_match} at {score}%)")
                    self.root.after(0, lambda: self.voice_status_label.configure(text=f"Voice Command: Unrecognized ({command})"))
                    continue

                print(f"Command interpreted as: '{best_match}'")
                self.root.after(0, lambda bm=best_match: self.voice_status_label.configure(text=f"Action: {bm}"))

                # Handle commands
                if best_match in ["camera on", "start camera", "begin detection"]:
                    self.detection_paused = False
                    self.app_state = AppState.IDLE   # 🔑 allow restart
                    self.root.after(0, self.start_detection)
                    continue


                elif best_match in ["volume up", "increase volume", "louder"]:
                    self.change_system_volume(0.1)

                elif best_match in ["volume down", "decrease volume", "softer"]:
                    self.change_system_volume(-0.1)

                elif best_match == "what song":
                    current_song = self.song_label.cget("text")
                    continue

                   # self.speak_blocking(f"The current song is {current_song}")

                if CONFIG["music_mode"] == "Local":
                    if best_match in ["pause", "pause music", "stop", "stop music"]:
                        self.root.after(0, self.toggle_pause_play)

                    elif best_match in ["play", "resume", "start music"]:
                        self.root.after(0, self.toggle_pause_play)

                    elif best_match in ["next song", "next", "skip"]:
                        self.root.after(0, self.play_next_song)

                    elif best_match in ["previous song", "previous", "go back"]:
                        self.root.after(0, self.play_previous_song)
                
                elif CONFIG["music_mode"] == "Spotify" and self.is_spotify_premium:
                    if best_match in ["pause", "pause music", "stop", "stop music"]:
                        self.root.after(0, self.toggle_pause_play)

                    elif best_match in ["play", "resume", "start music"]:
                        self.root.after(0, self.toggle_pause_play)

                    elif best_match in ["next song", "next", "skip"]:
                        self.root.after(0, self.play_next_song)

                    elif best_match in ["previous song", "previous", "go back"]:
                        self.root.after(0, self.play_previous_song)
                        

            except (sr.UnknownValueError, sr.WaitTimeoutError):
                pass
            except Exception as e:
                print(f"Voice loop error: {e}")
            finally:
                            
                if self.is_running:
                    if time.time() - getattr(self, "_last_voice_seen_time", 0) > 1.0:
                        self.root.after(0, lambda: self.voice_status_label.configure(text="Voice Command: Ready"))



    # ---------------------------
    # UI helpers
    # ---------------------------
    def open_playlist_url(self, event):
        if self.current_playlist_url:
            webbrowser.open_new(self.current_playlist_url)

    def update_voice_status(self, text, hold_ms=2500):
        try:
            self.voice_status_label.configure(text=text, text_color="white")

            self._last_voice_seen_time = time.time()

            if getattr(self, "_voice_reset_after_id", None):
                try:
                    self.root.after_cancel(self._voice_reset_after_id)
                except Exception:
                    pass
                self._voice_reset_after_id = None

            def _reset():
                try:
                    self.voice_status_label.configure(
                        text="Voice Command: Ready",
                        text_color="white"   # reset to white
                    )
                except Exception:
                    pass
                finally:
                    self._voice_reset_after_id = None

            self._voice_reset_after_id = self.root.after(hold_ms, _reset)
        except Exception as e:
            print(f"update_voice_status error: {e}")

        

    # In main.py
    def set_music_mode(self, mode):
        """Switch between Local and Spotify modes."""
        if CONFIG["music_mode"] == "Spotify":
            self.is_running_monitor = False
            if self.sp and self.spotify_device_id:
                try:
                    self.sp.pause_playback(device_id=self.spotify_device_id)
                except Exception as e:
                    print(f"Could not pause Spotify on mode switch: {e}")
        # ----------------------------------------------------
        is_first_selection = self.app_state == AppState.IDLE

        if CONFIG["music_mode"] == "Local" and mode != "Local":
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                self.is_paused = False
                self.is_manually_skipping = False
            except Exception as e:
                print(f"Error stopping local music on mode switch: {e}")

        if self.app_state == AppState.AUTH_ERROR and mode == "Local":
            self.app_state = AppState.IDLE

        if CONFIG["music_mode"] == mode and not is_first_selection:
            self.start_detection()
            return

        CONFIG["music_mode"] = mode
        print(f"Music mode switched to: {mode}")
        self.mode_label.configure(text=f"Mode: {mode}")
        self.update_mode_button_visuals()

        if mode == "Spotify":
            missing = [k for k in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI") if not os.getenv(k)]
            if missing:
                self.placeholder_label.configure(text=f"Spotify env missing: {', '.join(missing)}")
                self.app_state = AppState.AUTH_ERROR
                self.sp = None
                return

            if not self.sp or not self.is_spotify_token_valid():
                self.authenticate_spotify()
                if not self.sp:
                    self.webcam_label.place_forget()  # Hide the camera view
                    self.progress_bar.pack_forget()   # Hide the progress bar

                    self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")

                    self.play_pause_button.configure(state="disabled")
                    self.next_button.configure(state="disabled")
                    self.previous_button.configure(state="disabled")
                    
                    return # Exit the function

        self.start_detection()


    def set_language(self, lang):
        if CONFIG["current_language"] == lang:
            return
        CONFIG["current_language"] = lang
        print(f"Language switched to: {lang}")
        self.lang_label.configure(text=f"Language: {lang.capitalize()}")
        self.update_mode_button_visuals()
        
        if self.app_state in [AppState.PLAYING, AppState.SUGGESTED] and self.target_emotion_for_playback:
            print(f"Finding new music for '{self.target_emotion_for_playback}' in '{lang}'...")
            
            # This simpler logic will always start new music automatically.
            if CONFIG["music_mode"] == "Local":
                self.play_local_music()
            else:
                self.suggest_spotify_playlist()

    # ---------------------------
    # Main loop & Close app
    # ---------------------------
    def update(self):
        if not self.is_running:
            return
        self.process_analysis_queue()
        try:
            if getattr(self, "inquiry_pending", None):
                if time.time() - (self.inquiry_start_time or 0) >= self.inquiry_timeout_seconds:
                    pending = self.inquiry_pending
                    print(f"Inquiry timed out for '{pending}'. Falling back to neutral.")
                    self.inquiry_pending = None
                    self.inquiry_start_time = None
                    self.target_emotion_for_playback = "neutral"

                    self.target_emotion_label.configure(text="Playing For: Neutral (default)")
                    self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
                    self.placeholder_label.configure(text="No reply detected — playing calming music by default.")

                    if CONFIG["music_mode"] == "Spotify":
                        self.suggest_spotify_playlist()
                    else:
                        self.play_local_music()

                    self.detection_paused = False    
        except Exception as e:
            print(f"Inquiry timeout check error: {e}")

        if self.app_state == AppState.DETECTING:
            self.update_webcam_feed()
            self.handle_detection_timing()
        try:
            if self.is_manually_skipping and pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                self.is_manually_skipping = False
        except Exception:
            pass
        self.check_local_music_end()
        self.root.after(20, self.update)

    def update_webcam_feed(self):
        if not hasattr(self, 'cap') or not getattr(self, 'cap', None) or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            self.app_state = AppState.CAMERA_ERROR
            self.placeholder_label.configure(text="Error: Failed to get frame.")
            return
        self.display_frame(frame)

    def on_closing(self):
        try:
            print("Releasing player lock on the server...")
            requests.post(
                f"{BASE_API_URL}/release_lock",
                json={"email": self.user_email},
                timeout=2  # Set a short timeout to not delay closing
            )
            print("Lock released.")
        except Exception as e:
            print(f"Could not release player lock: {e}")

        self.is_running_monitor = False
        self.is_running = False
        time.sleep(0.2)
        try:
            if hasattr(self, 'cap') and self.cap.isOpened():
                self.cap.release()
        except Exception:
            pass
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception:
            pass
        self.root.destroy()

# ---------------------------
# Run app
# ---------------------------
if __name__ == "__main__":
    root = ctk.CTk()
    root.configure(fg_color=COLOR_BG_DARK)

    user_email_arg = sys.argv[1] if len(sys.argv) > 1 else "guest@example.com"
    default_language_arg = sys.argv[2] if len(sys.argv) > 2 else "english"

    spotify_token_arg = sys.argv[3] if len(sys.argv) > 3 else ""
    spotify_refresh_arg = sys.argv[4] if len(sys.argv) > 4 else ""
    spotify_expires_at_arg = sys.argv[5] if len(sys.argv) > 5 else ""
    is_premium_arg = sys.argv[6] if len(sys.argv) > 6 else "False"

    app = EmotionMusicPlayerApp(
        root,
        user_email=user_email_arg,
        default_language=default_language_arg
    )

    app.spotify_access_token = spotify_token_arg
    app.spotify_refresh_token = spotify_refresh_arg
    app.is_spotify_premium = (is_premium_arg.lower() == 'true') # Convert string to boolean
    try:
        app.spotify_expires_at = int(spotify_expires_at_arg)
    except Exception:
        app.spotify_expires_at = 0

    root.mainloop()