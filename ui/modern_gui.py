import tkinter as tk

class EmotionPlayerUI:

    def __init__(self, controller):
        self.controller = controller

        self.root = tk.Tk()
        self.root.title("Emotion AI Music Player")
        self.root.geometry("1200x700")

        self.build_ui()

    def build_ui(self):
        label = tk.Label(
            self.root,
            text="GUI CONNECTED SUCCESSFULLY",
            font=("Segoe UI", 20)
        )
        label.pack(expand=True)

    def run(self):
        self.root.mainloop()