# Smarter Auto Clicker v3 - For Learning Purposes
# Controls: Customizable hotkey = Start/Stop | ESC = Emergency stop

import customtkinter as ctk
import pyautogui
from pynput import keyboard, mouse as pynput_mouse
import threading, random, math, time, tkinter as tk
import ctypes
import ctypes.wintypes
import json, csv, os, winsound
from datetime import datetime
from PIL import ImageGrab

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

HELP_TEXT = chr(10).join([
    "SMARTER AUTO CLICKER v3 - HELP GUIDE",
    "========================================",
    "",
    "QUICK START:",
    "1. Set your click interval (Min/Max seconds)",
    "2. Choose a Click Target mode",
    "3. Press F6 (or your hotkey) to Start/Stop",
    "4. Press ESC for Emergency Stop",
    "",
    "CLICK TARGET MODES:",
    "- At cursor position: Clicks wherever your mouse is",
    "- Random within area: Clicks randomly inside X/Y/W/H box",
    "- Background (locked to window): Click a window even",
    "  when behind other windows. Use Pick Window first!",
    "  TIP: Enable Hardware Clicks for games.",
    "- Multi-point sequence: Add points, clicks cycle through",
    "- Multiple click zones: Weighted rectangular click areas",
    "",
    "BACKGROUND MODE TIPS:",
    "- Hardware Clicks ON = moves real cursor + sends real",
    "  clicks. Works with most games but briefly moves mouse.",
    "- Hardware Clicks OFF = PostMessage (silent, invisible).",
    "  Only works with standard Windows apps, NOT games.",
    "",
    "KEY FEATURES:",
    "- Profiles: Save/load all settings as named presets",
    "- Speed Ramping: Gradually change speed over N clicks",
    "- Keyboard Injection: Auto-press keys at intervals",
    "- Break System: Periodic pauses to appear human",
    "- Pixel Watch: Auto-stop when a pixel color changes",
    "- Anti-AFK: Random jitter to prevent idle detection",
    "- Session Log: Record all clicks to CSV",
    "- Mini Mode: Compact always-on-top window",
    "- Sound Alerts: Beeps for breaks, stops, and alerts",
])



# ---------------------------------------------------------------------------
# Human-like mouse movement using Bezier curves
# ---------------------------------------------------------------------------

def bezier_point(t, points):
    n = len(points) - 1
    x, y = 0.0, 0.0
    for i, (px, py) in enumerate(points):
        coeff = math.comb(n, i) * (t ** i) * ((1 - t) ** (n - i))
        x += coeff * px
        y += coeff * py
    return x, y


def human_move(x_end, y_end, duration_range=(0.15, 0.45)):
    x_start, y_start = pyautogui.position()
    dist = math.hypot(x_end - x_start, y_end - y_start)
    if dist < 2:
        return
    base = random.uniform(*duration_range)
    duration = base * (dist / 500) + random.uniform(0.01, 0.05)
    duration = max(0.05, min(duration, 1.5))
    num_control = random.choice([1, 2])
    controls = [(x_start, y_start)]
    for _ in range(num_control):
        mid_t = random.uniform(0.25, 0.75)
        mx = x_start + (x_end - x_start) * mid_t
        my = y_start + (y_end - y_start) * mid_t
        spread = dist * random.uniform(0.05, 0.25)
        mx += random.uniform(-spread, spread)
        my += random.uniform(-spread, spread)
        controls.append((mx, my))
    controls.append((x_end, y_end))
    steps = max(10, int(dist / 5))
    start_time = time.perf_counter()
    for i in range(1, steps + 1):
        if time.perf_counter() - start_time >= duration:
            break
        t = i / steps
        t = t * t * (3 - 2 * t)
        bx, by = bezier_point(t, controls)
        bx += random.gauss(0, 0.5)
        by += random.gauss(0, 0.5)
        pyautogui.moveTo(int(bx), int(by), _pause=False)
        edge_factor = 1 + 2 * (1 - 4 * (t - 0.5) ** 2)
        time.sleep(max(0.001, (duration / steps) * edge_factor))
    pyautogui.moveTo(int(x_end), int(y_end), _pause=False)


# ---------------------------------------------------------------------------
# Random interval generation (Gaussian, not uniform)
# ---------------------------------------------------------------------------

def random_interval(min_val, max_val):
    mean = (min_val + max_val) / 2
    std = (max_val - min_val) / 4
    val = max(min_val, min(max_val, random.gauss(mean, std)))
    if random.random() < 0.10:
        val += random.uniform(0.05, 0.3)
    return val


# ---------------------------------------------------------------------------
# Click target position
# ---------------------------------------------------------------------------

def get_click_position(mode, area):
    if mode == "cursor":
        cx, cy = pyautogui.position()
        return int(cx + random.gauss(0, 2)), int(cy + random.gauss(0, 2))
    ax, ay, aw, ah = area
    gx = max(ax, min(ax + aw, random.gauss(ax + aw / 2, aw / 6)))
    gy = max(ay, min(ay + ah, random.gauss(ay + ah / 2, ah / 6)))
    return int(gx), int(gy)

# ---------------------------------------------------------------------------
# Win32 Background Click Helpers
# ---------------------------------------------------------------------------

user32 = ctypes.windll.user32

# Set proper argtypes/restype for Win32 HWND functions (critical on 64-bit)
HWND = ctypes.wintypes.HWND
POINT = ctypes.wintypes.POINT
UINT = ctypes.wintypes.UINT
BOOL = ctypes.wintypes.BOOL
LPARAM = ctypes.wintypes.LPARAM
WPARAM = ctypes.wintypes.WPARAM
RECT = ctypes.wintypes.RECT

user32.WindowFromPoint.argtypes = [POINT]
user32.WindowFromPoint.restype = HWND

user32.GetAncestor.argtypes = [HWND, UINT]
user32.GetAncestor.restype = HWND

user32.ChildWindowFromPointEx.argtypes = [HWND, POINT, UINT]
user32.ChildWindowFromPointEx.restype = HWND

user32.IsWindow.argtypes = [HWND]
user32.IsWindow.restype = BOOL

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.GetClassNameW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

# Callback type for EnumChildWindows
WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
user32.EnumChildWindows.argtypes = [HWND, WNDENUMPROC, LPARAM]
user32.EnumChildWindows.restype = BOOL

user32.GetParent.argtypes = [HWND]
user32.GetParent.restype = HWND

user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = BOOL

user32.ScreenToClient.argtypes = [HWND, ctypes.POINTER(POINT)]
user32.ScreenToClient.restype = BOOL

user32.ClientToScreen.argtypes = [HWND, ctypes.POINTER(POINT)]
user32.ClientToScreen.restype = BOOL

user32.GetClientRect.argtypes = [HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = BOOL

user32.GetWindowTextLengthW.argtypes = [HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = BOOL

user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = BOOL

user32.GetWindowLongW.argtypes = [HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long

user32.SetWindowLongW.argtypes = [HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long

user32.mouse_event.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
                                ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
                                ctypes.c_size_t]
user32.mouse_event.restype = None

WM_MOUSEMOVE     = 0x0200
WM_LBUTTONDOWN   = 0x0201
WM_LBUTTONUP     = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN   = 0x0204
WM_RBUTTONUP     = 0x0205
MK_LBUTTON       = 0x0001
MK_RBUTTON       = 0x0002

def _make_lparam(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

def _find_child_at_screen(parent_hwnd, screen_x, screen_y):
    pt = ctypes.wintypes.POINT(screen_x, screen_y)
    user32.ScreenToClient(parent_hwnd, ctypes.byref(pt))
    child = user32.ChildWindowFromPointEx(parent_hwnd, pt, 0)
    if child and child != parent_hwnd:
        pt2 = ctypes.wintypes.POINT(screen_x, screen_y)
        user32.ScreenToClient(child, ctypes.byref(pt2))
        deeper = user32.ChildWindowFromPointEx(child, pt2, 0)
        if deeper and deeper != child and user32.IsWindow(deeper):
            return deeper
        return child
    return parent_hwnd

def _client_to_screen(hwnd, cx, cy):
    pt = ctypes.wintypes.POINT(cx, cy)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y

def _prepare_click(top_hwnd, client_x, client_y):
    sx, sy = _client_to_screen(top_hwnd, client_x, client_y)
    target = _find_child_at_screen(top_hwnd, sx, sy)
    pt = ctypes.wintypes.POINT(sx, sy)
    user32.ScreenToClient(target, ctypes.byref(pt))
    return target, pt.x, pt.y

# Background click: post directly to the captured window HWND.
# Minimal approach: just mouse down + up. No activation messages.
# The user picks the exact window (e.g. OSRS game canvas) during Pick Window.

user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = ctypes.c_long

def _bg_post(hwnd, msg, wp, lp, use_send=False):
    if use_send:
        return user32.SendMessageW(hwnd, msg, wp, lp)
    return user32.PostMessageW(hwnd, msg, wp, lp)

def _child_to_root_coords(child_hwnd, root_hwnd, cx, cy):
    if child_hwnd == root_hwnd:
        return cx, cy
    pt = ctypes.wintypes.POINT(cx, cy)
    user32.ClientToScreen(child_hwnd, ctypes.byref(pt))
    user32.ScreenToClient(root_hwnd, ctypes.byref(pt))
    return pt.x, pt.y

def bg_click_left(hwnd, x, y, use_send=False, root_hwnd=None):
    target = root_hwnd if root_hwnd else hwnd
    if root_hwnd and root_hwnd != hwnd:
        x, y = _child_to_root_coords(hwnd, root_hwnd, x, y)
    lp = _make_lparam(x, y)
    _bg_post(target, WM_MOUSEMOVE, 0, lp, use_send)
    time.sleep(random.uniform(0.01, 0.03))
    r1 = _bg_post(target, WM_LBUTTONDOWN, MK_LBUTTON, lp, use_send)
    time.sleep(random.uniform(0.03, 0.08))
    r2 = _bg_post(target, WM_LBUTTONUP, 0, lp, use_send)
    return r1, r2

def bg_click_right(hwnd, x, y, use_send=False, root_hwnd=None):
    target = root_hwnd if root_hwnd else hwnd
    if root_hwnd and root_hwnd != hwnd:
        x, y = _child_to_root_coords(hwnd, root_hwnd, x, y)
    lp = _make_lparam(x, y)
    _bg_post(target, WM_MOUSEMOVE, 0, lp, use_send)
    time.sleep(random.uniform(0.01, 0.03))
    r1 = _bg_post(target, WM_RBUTTONDOWN, MK_RBUTTON, lp, use_send)
    time.sleep(random.uniform(0.03, 0.08))
    r2 = _bg_post(target, WM_RBUTTONUP, 0, lp, use_send)
    return r1, r2

def bg_click_double(hwnd, x, y, use_send=False, root_hwnd=None):
    target = root_hwnd if root_hwnd else hwnd
    if root_hwnd and root_hwnd != hwnd:
        x, y = _child_to_root_coords(hwnd, root_hwnd, x, y)
    lp = _make_lparam(x, y)
    _bg_post(target, WM_MOUSEMOVE, 0, lp, use_send)
    time.sleep(random.uniform(0.01, 0.03))
    _bg_post(target, WM_LBUTTONDOWN, MK_LBUTTON, lp, use_send)
    time.sleep(random.uniform(0.02, 0.05))
    _bg_post(target, WM_LBUTTONUP, 0, lp, use_send)
    time.sleep(random.uniform(0.02, 0.06))
    _bg_post(target, WM_LBUTTONDBLCLK, MK_LBUTTON, lp, use_send)
    time.sleep(random.uniform(0.02, 0.05))
    _bg_post(target, WM_LBUTTONUP, 0, lp, use_send)

MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010

def hw_click_left(hwnd, x, y):
    sx, sy = _client_to_screen(hwnd, x, y)
    orig = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(orig))
    user32.SetCursorPos(sx, sy)
    time.sleep(random.uniform(0.01, 0.02))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.03, 0.08))
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(random.uniform(0.01, 0.02))
    user32.SetCursorPos(orig.x, orig.y)

def hw_click_right(hwnd, x, y):
    sx, sy = _client_to_screen(hwnd, x, y)
    orig = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(orig))
    user32.SetCursorPos(sx, sy)
    time.sleep(random.uniform(0.01, 0.02))
    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.03, 0.08))
    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    time.sleep(random.uniform(0.01, 0.02))
    user32.SetCursorPos(orig.x, orig.y)

def hw_click_double(hwnd, x, y):
    sx, sy = _client_to_screen(hwnd, x, y)
    orig = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(orig))
    user32.SetCursorPos(sx, sy)
    time.sleep(random.uniform(0.01, 0.02))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.02, 0.04))
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(random.uniform(0.02, 0.05))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.02, 0.04))
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(random.uniform(0.01, 0.02))
    user32.SetCursorPos(orig.x, orig.y)

def get_window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def find_deepest_child(root_hwnd):
    children = []
    def callback(hwnd, lparam):
        children.append(hwnd)
        return True
    user32.EnumChildWindows(root_hwnd, WNDENUMPROC(callback), 0)
    return children

def get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def screen_to_client(hwnd, sx, sy):
    pt = ctypes.wintypes.POINT(sx, sy)
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    return pt.x, pt.y

def get_bg_click_position(hwnd, region):
    if region is not None:
        rx, ry, rw, rh = region
        sx = max(rx, min(rx + rw, random.gauss(rx + rw / 2, rw / 6)))
        sy = max(ry, min(ry + rh, random.gauss(ry + rh / 2, rh / 6)))
        cx, cy = screen_to_client(hwnd, int(sx), int(sy))
        return max(0, cx), max(0, cy)
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    cw = rect.right - rect.left
    ch = rect.bottom - rect.top
    if cw < 5 or ch < 5:
        return 10, 10
    gx = max(5, min(cw - 5, random.gauss(cw / 2, cw / 6)))
    gy = max(5, min(ch - 5, random.gauss(ch / 2, ch / 6)))
    return int(gx), int(gy)

# ---------------------------------------------------------------------------
# Hotkey name helpers
# ---------------------------------------------------------------------------

def key_to_name(key):
    if isinstance(key, keyboard.Key):
        return key.name.replace("_", " ").title()
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.upper()
        if key.vk is not None:
            return "VK_{}".format(key.vk)
    return str(key)

def mouse_button_to_name(button):
    names = {
        "Button.left": "Mouse Left",
        "Button.right": "Mouse Right",
        "Button.middle": "Mouse Middle",
        "Button.x1": "Mouse X1 (Back)",
        "Button.x2": "Mouse X2 (Forward)",
    }
    return names.get(str(button), str(button))


# ---------------------------------------------------------------------------
# Region Selector (Snipping Tool style overlay)
# ---------------------------------------------------------------------------

class RegionSelector:
    def __init__(self, callback):
        self.callback = callback
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        # Get virtual screen bounds (spans ALL monitors)
        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79
        self.vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.3)
        self.root.configure(bg="black")
        self.root.config(cursor="crosshair")
        # Position window to cover ALL monitors
        self.root.geometry("{}x{}+{}+{}".format(vw, vh, self.vx, self.vy))
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0,
            width=vw, height=vh)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self._cancel())
        msg = "Click and drag to select region" + chr(10) + "Press ESC to cancel"
        self.canvas.create_text(vw // 2, vh // 2, text=msg,
            fill="white", font=("Arial", 24, "bold"), justify="center")

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#00ff00", width=3)

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        w, h = x2 - x1, y2 - y1
        self.root.destroy()
        if w > 10 and h > 10:
            # Convert canvas coords to screen coords (add virtual screen offset)
            self.callback(x1 + self.vx, y1 + self.vy, w, h)

    def _cancel(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Region Overlay - persistent semi-transparent border showing click area
# ---------------------------------------------------------------------------

class RegionOverlay:
    def __init__(self):
        self._win = None

    def show(self, x, y, w, h):
        self.hide()
        self._win = tk.Toplevel()
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 0.35)
        self._win.geometry("{}x{}+{}+{}".format(w, h, x, y))
        canvas = tk.Canvas(self._win, width=w, height=h, bg="black", highlightthickness=0)
        canvas.pack()
        canvas.create_rectangle(2, 2, w - 2, h - 2, outline="#00ff00", width=3, fill="")
        canvas.create_text(w // 2, h // 2, text="Click Zone", fill="#00ff00",
            font=("Arial", 10), anchor="center")
        # Make clicks pass through
        self._win.wm_attributes("-disabled", True)
        hwnd = ctypes.windll.user32.GetParent(self._win.winfo_id())
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex_style | 0x80000 | 0x20)

    def hide(self):
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None

    @property
    def visible(self):
        return self._win is not None


# ---------------------------------------------------------------------------
# Profile Manager - save/load configuration presets as JSON
# ---------------------------------------------------------------------------

class ProfileManager:
    @staticmethod
    def list_profiles():
        profiles = []
        if os.path.isdir(PROFILES_DIR):
            for f in os.listdir(PROFILES_DIR):
                if f.endswith(".json"):
                    profiles.append(f[:-5])
        return sorted(profiles)

    @staticmethod
    def save(name, data):
        path = os.path.join(PROFILES_DIR, name + ".json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(name):
        path = os.path.join(PROFILES_DIR, name + ".json")
        with open(path, "r") as f:
            return json.load(f)

    @staticmethod
    def delete(name):
        path = os.path.join(PROFILES_DIR, name + ".json")
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# Session Logger - records click data for CSV export
# ---------------------------------------------------------------------------

class SessionLogger:
    def __init__(self):
        self.rows = []
        self.enabled = False

    def log(self, x, y, interval, click_type, mode):
        if not self.enabled:
            return
        self.rows.append({
            "timestamp": datetime.now().isoformat(),
            "x": x, "y": y,
            "interval": round(interval, 4),
            "click_type": click_type,
            "mode": mode,
        })

    def export(self):
        if not self.rows:
            return None
        fname = "session_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        path = os.path.join(LOGS_DIR, fname)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "x", "y", "interval", "click_type", "mode"])
            writer.writeheader()
            writer.writerows(self.rows)
        return path

    def clear(self):
        self.rows = []


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class AutoClickerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smarter Auto Clicker v3")
        self.geometry("500x900")
        self.resizable(False, False)

        self.running = False
        self.click_count = 0
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.selected_region = None
        self.target_hwnd = None
        self.target_root = None
        self._picking_window = False

        # Hotkey config
        self._hotkey = keyboard.Key.f6
        self._hotkey_name = "F6"
        self._hotkey_is_mouse = False
        self._recording_hotkey = False
        self._kb_listener = None
        self._mouse_listener = None

        # New feature state
        self.session_logger = SessionLogger()
        self.region_overlay = RegionOverlay()
        self.click_zones = []        # list of (x, y, w, h, weight)
        self.click_sequence = []     # list of (x, y)
        self._seq_index = 0
        self.key_injections = []     # list of (key_str, every_n)
        self._pixel_watch = None     # (x, y, r, g, b) or None
        self._prayer_interval = 3000 # prayer flick interval in ms (default 5-tick)
        self._session_start = None
        self._mini_win = None
        self._timer_id = None

        self._build_gui()
        self._start_hotkey_listener()

    # ----- GUI Construction -----

    def _build_gui(self):
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(self, text="Smarter Auto Clicker v3",
                              font=ctk.CTkFont(size=22, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=(15, 3))
        subtitle = ctk.CTkLabel(self, text="Human-like automation for learning",
                                font=ctk.CTkFont(size=12), text_color="gray")
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 8))

        content = ctk.CTkScrollableFrame(self, label_text="")
        content.grid(row=2, column=0, padx=12, pady=(0, 5), sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._content = content

        row = 0

        # ====== TARGET REGION / WINDOW ======
        lbl = ctk.CTkLabel(content, text="Target Region / Window",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Choose where clicks land. Select Region = screen area, Pick Window = background clicking.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        region_frm = ctk.CTkFrame(content, fg_color="transparent")
        region_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        self.btn_select_region = ctk.CTkButton(region_frm, text="Select Region",
            command=self._select_region, height=30, font=ctk.CTkFont(size=11),
            fg_color="#6c5ce7", hover_color="#5a4bd1")
        self.btn_select_region.pack(side="left", padx=2)
        self.btn_pick_window = ctk.CTkButton(region_frm, text="Pick Window",
            command=self._pick_window, height=30, font=ctk.CTkFont(size=11),
            fg_color="#e17055", hover_color="#d35400")
        self.btn_pick_window.pack(side="left", padx=2)
        self.btn_clear_region = ctk.CTkButton(region_frm, text="Clear", width=50,
            command=self._clear_region, height=30, font=ctk.CTkFont(size=11),
            fg_color="#636e72", hover_color="#535c60")
        self.btn_clear_region.pack(side="left", padx=2)
        self.btn_test_click = ctk.CTkButton(region_frm, text="Test Click", width=70,
            command=self._test_bg_click, height=30, font=ctk.CTkFont(size=11),
            fg_color="#0984e3", hover_color="#0769b5")
        self.btn_test_click.pack(side="left", padx=2)
        row += 1

        self.lbl_region_info = ctk.CTkLabel(content, text="No region/window selected",
            font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_region_info.grid(row=row, column=0, columnspan=4, padx=15, pady=(0, 5), sticky="w")
        row += 1

        # ====== PROFILE PRESETS ======
        lbl = ctk.CTkLabel(content, text="Profile Presets",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Save/load all your settings as named presets (stored as JSON files).",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        prof_frm = ctk.CTkFrame(content, fg_color="transparent")
        prof_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        self.profile_var = ctk.StringVar(value="(none)")
        profiles = ProfileManager.list_profiles()
        self.profile_menu = ctk.CTkOptionMenu(prof_frm, variable=self.profile_var,
            values=["(none)"] + profiles, width=140)
        self.profile_menu.pack(side="left", padx=2)
        ctk.CTkButton(prof_frm, text="Load", width=50, height=28,
            command=self._load_profile, fg_color="#0984e3", hover_color="#0769b5").pack(side="left", padx=2)
        ctk.CTkButton(prof_frm, text="Save", width=50, height=28,
            command=self._save_profile, fg_color="#00b894", hover_color="#00a381").pack(side="left", padx=2)
        ctk.CTkButton(prof_frm, text="Delete", width=55, height=28,
            command=self._delete_profile, fg_color="#d63031", hover_color="#b71c1c").pack(side="left", padx=2)
        row += 1

        # ====== CLICK INTERVAL + SPEED RAMPING ======
        lbl = ctk.CTkLabel(content, text="Click Interval (seconds)",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Time between clicks. Uses Gaussian distribution for natural variation.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        interval_frm = ctk.CTkFrame(content, fg_color="transparent")
        interval_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(interval_frm, text="Min:").pack(side="left", padx=(0, 3))
        self.var_min_interval = ctk.CTkEntry(interval_frm, width=70, placeholder_text="0.8")
        self.var_min_interval.pack(side="left", padx=3)
        self.var_min_interval.insert(0, "0.8")
        ctk.CTkLabel(interval_frm, text="Max:").pack(side="left", padx=(15, 3))
        self.var_max_interval = ctk.CTkEntry(interval_frm, width=70, placeholder_text="2.5")
        self.var_max_interval.pack(side="left", padx=3)
        self.var_max_interval.insert(0, "2.5")
        row += 1

        # Speed Ramping
        self.var_ramp_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(content, text="Enable speed ramping",
            variable=self.var_ramp_enabled).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        ramp_frm = ctk.CTkFrame(content, fg_color="transparent")
        ramp_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(ramp_frm, text="Start mult:").pack(side="left", padx=(0, 2))
        self.var_ramp_start = ctk.CTkEntry(ramp_frm, width=50, placeholder_text="1.0")
        self.var_ramp_start.pack(side="left", padx=2)
        self.var_ramp_start.insert(0, "1.0")
        ctk.CTkLabel(ramp_frm, text="End:").pack(side="left", padx=(8, 2))
        self.var_ramp_end = ctk.CTkEntry(ramp_frm, width=50, placeholder_text="0.5")
        self.var_ramp_end.pack(side="left", padx=2)
        self.var_ramp_end.insert(0, "0.5")
        ctk.CTkLabel(ramp_frm, text="Over N:").pack(side="left", padx=(8, 2))
        self.var_ramp_clicks = ctk.CTkEntry(ramp_frm, width=55, placeholder_text="200")
        self.var_ramp_clicks.pack(side="left", padx=2)
        self.var_ramp_clicks.insert(0, "200")
        row += 1


        # ====== CLICK TYPE ======
        lbl = ctk.CTkLabel(content, text="Click Type",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Choose Left click, Right click, or Double click.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        self.var_click_type = ctk.StringVar(value="left")
        type_frm = ctk.CTkFrame(content, fg_color="transparent")
        type_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        self.click_type_seg = ctk.CTkSegmentedButton(type_frm, values=["Left", "Right", "Double"],
                                                      command=self._on_click_type)
        self.click_type_seg.set("Left")
        self.click_type_seg.pack(fill="x", padx=5)
        row += 1

        # ====== CLICK TARGET MODE ======
        lbl = ctk.CTkLabel(content, text="Click Target",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Cursor = clicks at mouse position, Area = random within rectangle, Background = locked to a window.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        self.var_target_mode = ctk.StringVar(value="cursor")
        target_frm = ctk.CTkFrame(content, fg_color="transparent")
        target_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        for txt, val in [("At cursor position", "cursor"), ("Random within area", "area"),
                         ("Background (locked to window)", "background"),
                         ("Multi-point sequence", "sequence"), ("Multiple click zones", "zones"),
                         ("1-Tick Prayer Flick", "prayer")]:
            ctk.CTkRadioButton(target_frm, text=txt, variable=self.var_target_mode,
                               value=val, command=self._toggle_area).pack(anchor="w", pady=1)
        row += 1

        # Area X/Y/W/H
        area_frm = ctk.CTkFrame(content, fg_color="transparent")
        area_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        self.area_entries = {}
        for lbl_text, default in [("X", "100"), ("Y", "100"), ("W", "300"), ("H", "300")]:
            ctk.CTkLabel(area_frm, text=lbl_text + ":").pack(side="left", padx=(4, 1))
            e = ctk.CTkEntry(area_frm, width=55, placeholder_text=default)
            e.pack(side="left", padx=(0, 4))
            e.insert(0, default)
            self.area_entries[lbl_text] = e
        row += 1
        self._toggle_area()

        # ====== MULTI-CLICK ZONES ======
        lbl = ctk.CTkLabel(content, text="Click Zones (for zones mode)",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Define weighted rectangular areas. Higher weight = more clicks in that zone.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        zones_btn_frm = ctk.CTkFrame(content, fg_color="transparent")
        zones_btn_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkButton(zones_btn_frm, text="Add Zone", width=80, height=28,
            command=self._add_zone, fg_color="#6c5ce7", hover_color="#5a4bd1").pack(side="left", padx=2)
        ctk.CTkButton(zones_btn_frm, text="Clear Zones", width=85, height=28,
            command=self._clear_zones, fg_color="#636e72", hover_color="#535c60").pack(side="left", padx=2)
        row += 1

        self.lbl_zones_info = ctk.CTkLabel(content, text="No zones defined",
            font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_zones_info.grid(row=row, column=0, columnspan=4, padx=15, pady=(0, 5), sticky="w")
        row += 1

        # ====== CLICK SEQUENCE ======
        lbl = ctk.CTkLabel(content, text="Click Sequence (for sequence mode)",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Ordered list of screen points. Clicks cycle through them in order.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        seq_btn_frm = ctk.CTkFrame(content, fg_color="transparent")
        seq_btn_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkButton(seq_btn_frm, text="Add Point", width=80, height=28,
            command=self._add_sequence_point, fg_color="#e17055", hover_color="#d35400").pack(side="left", padx=2)
        ctk.CTkButton(seq_btn_frm, text="Clear", width=55, height=28,
            command=self._clear_sequence, fg_color="#636e72", hover_color="#535c60").pack(side="left", padx=2)
        row += 1

        self.lbl_seq_info = ctk.CTkLabel(content, text="No sequence points",
            font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_seq_info.grid(row=row, column=0, columnspan=4, padx=15, pady=(0, 5), sticky="w")
        row += 1

        # ====== 1-TICK PRAYER FLICK ======
        lbl = ctk.CTkLabel(content, text="Prayer Flick Settings (for prayer mode)",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Automatically prayer flick every monster! Select the monster's attack speed in ticks.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        prayer_frm = ctk.CTkFrame(content, fg_color="transparent")
        prayer_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(prayer_frm, text="Monster attack speed:").pack(side="left", padx=(0, 4))
        self.var_prayer_speed = ctk.StringVar(value="5 ticks (3000ms)")
        self.prayer_speed_menu = ctk.CTkOptionMenu(prayer_frm,
            values=["2 ticks (1200ms)", "3 ticks (1800ms)", "4 ticks (2400ms)",
                    "5 ticks (3000ms)", "6 ticks (3600ms)", "7 ticks (4200ms)"],
            variable=self.var_prayer_speed, command=self._on_prayer_speed_change,
            width=160, height=28, fg_color="#6c5ce7", button_color="#5a4bd1",
            button_hover_color="#4a3dc1")
        self.prayer_speed_menu.pack(side="left", padx=4)
        row += 1

        self.lbl_prayer_info = ctk.CTkLabel(content,
            text="Flick interval: 3000ms  |  Press Start to begin flicking at cursor position.",
            font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_prayer_info.grid(row=row, column=0, columnspan=4, padx=15, pady=(0, 5), sticky="w")
        row += 1

        # ====== KEYBOARD INJECTION ======
        lbl = ctk.CTkLabel(content, text="Keyboard Injection",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Auto-press a key every N clicks (e.g. press 1 every 10 clicks for abilities).",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        kinj_frm = ctk.CTkFrame(content, fg_color="transparent")
        kinj_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(kinj_frm, text="Key:").pack(side="left", padx=(0, 2))
        self.var_inject_key = ctk.CTkEntry(kinj_frm, width=50, placeholder_text="1")
        self.var_inject_key.pack(side="left", padx=2)
        ctk.CTkLabel(kinj_frm, text="Every N clicks:").pack(side="left", padx=(8, 2))
        self.var_inject_every = ctk.CTkEntry(kinj_frm, width=50, placeholder_text="10")
        self.var_inject_every.pack(side="left", padx=2)
        ctk.CTkButton(kinj_frm, text="Add", width=40, height=26,
            command=self._add_key_injection, fg_color="#0984e3", hover_color="#0769b5").pack(side="left", padx=2)
        ctk.CTkButton(kinj_frm, text="Clear", width=45, height=26,
            command=self._clear_key_injections, fg_color="#636e72", hover_color="#535c60").pack(side="left", padx=2)
        row += 1

        self.lbl_inject_info = ctk.CTkLabel(content, text="No key injections",
            font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_inject_info.grid(row=row, column=0, columnspan=4, padx=15, pady=(0, 5), sticky="w")
        row += 1


        # ====== BREAK SYSTEM ======
        lbl = ctk.CTkLabel(content, text="Break System",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Take periodic pauses between click bursts to look more human.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        self.var_breaks_enabled = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(content, text="Enable breaks", variable=self.var_breaks_enabled).grid(
            row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        brk_frm1 = ctk.CTkFrame(content, fg_color="transparent")
        brk_frm1.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(brk_frm1, text="Clicks between:").pack(side="left", padx=(0, 3))
        self.var_break_clicks_min = ctk.CTkEntry(brk_frm1, width=55, placeholder_text="30")
        self.var_break_clicks_min.pack(side="left", padx=2)
        self.var_break_clicks_min.insert(0, "30")
        ctk.CTkLabel(brk_frm1, text="-").pack(side="left", padx=2)
        self.var_break_clicks_max = ctk.CTkEntry(brk_frm1, width=55, placeholder_text="80")
        self.var_break_clicks_max.pack(side="left", padx=2)
        self.var_break_clicks_max.insert(0, "80")
        row += 1

        brk_frm2 = ctk.CTkFrame(content, fg_color="transparent")
        brk_frm2.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(brk_frm2, text="Duration (sec):").pack(side="left", padx=(0, 3))
        self.var_break_dur_min = ctk.CTkEntry(brk_frm2, width=55, placeholder_text="3.0")
        self.var_break_dur_min.pack(side="left", padx=2)
        self.var_break_dur_min.insert(0, "3.0")
        ctk.CTkLabel(brk_frm2, text="-").pack(side="left", padx=2)
        self.var_break_dur_max = ctk.CTkEntry(brk_frm2, width=55, placeholder_text="12.0")
        self.var_break_dur_max.pack(side="left", padx=2)
        self.var_break_dur_max.insert(0, "12.0")
        row += 1

        # ====== MOUSE MOVEMENT ======
        lbl = ctk.CTkLabel(content, text="Mouse Movement",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Bezier curves = natural mouse paths. Disable for instant click positioning.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        self.var_human_mouse = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(content, text="Human-like Bezier curve movement",
            variable=self.var_human_mouse).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        # ====== BACKGROUND CLICK METHOD ======
        lbl = ctk.CTkLabel(content, text="Background Click Method",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        self.var_hw_clicks = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(content, text="Use hardware clicks (more compatible)",
            variable=self.var_hw_clicks).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        ctk.CTkLabel(content, text="ON = moves cursor + real clicks (works with games)  |  OFF = PostMessage (silent)",
            font=ctk.CTkFont(size=10), text_color="gray").grid(row=row, column=0, columnspan=4, padx=20, pady=(0, 3), sticky="w")
        row += 1

        self.var_use_sendmsg = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(content, text="Use SendMessage (synchronous, try if PostMessage fails)",
            variable=self.var_use_sendmsg).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        self.var_bg_debug = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(content, text="Debug output (print click info to console)",
            variable=self.var_bg_debug).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        # ====== SESSION TIMER ======
        lbl = ctk.CTkLabel(content, text="Session Timer",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Set a time limit in minutes. The clicker auto-stops when time runs out.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        timer_frm = ctk.CTkFrame(content, fg_color="transparent")
        timer_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(timer_frm, text="Auto-stop after (min):").pack(side="left", padx=(0, 3))
        self.var_session_limit = ctk.CTkEntry(timer_frm, width=60, placeholder_text="(none)")
        self.var_session_limit.pack(side="left", padx=3)
        row += 1

        # ====== ANTI-AFK JITTER ======
        lbl = ctk.CTkLabel(content, text="Anti-AFK Jitter",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Tiny random mouse movements at intervals to avoid idle/AFK detection.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        self.var_afk_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(content, text="Enable anti-AFK jitter",
            variable=self.var_afk_enabled).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        afk_frm = ctk.CTkFrame(content, fg_color="transparent")
        afk_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(afk_frm, text="Jitter every (sec):").pack(side="left", padx=(0, 3))
        self.var_afk_interval = ctk.CTkEntry(afk_frm, width=55, placeholder_text="30")
        self.var_afk_interval.pack(side="left", padx=3)
        self.var_afk_interval.insert(0, "30")
        row += 1


        # ====== CONDITIONAL STOP (PIXEL WATCH) ======
        lbl = ctk.CTkLabel(content, text="Conditional Stop (Pixel Watch)",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Pick a pixel on screen. Auto-stops when its color changes beyond tolerance.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        pixel_frm = ctk.CTkFrame(content, fg_color="transparent")
        pixel_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkButton(pixel_frm, text="Pick Pixel", width=80, height=28,
            command=self._pick_pixel, fg_color="#e17055", hover_color="#d35400").pack(side="left", padx=2)
        ctk.CTkButton(pixel_frm, text="Clear", width=50, height=28,
            command=self._clear_pixel, fg_color="#636e72", hover_color="#535c60").pack(side="left", padx=2)
        ctk.CTkLabel(pixel_frm, text="Tolerance:").pack(side="left", padx=(8, 2))
        self.var_pixel_tolerance = ctk.CTkEntry(pixel_frm, width=40, placeholder_text="30")
        self.var_pixel_tolerance.pack(side="left", padx=2)
        self.var_pixel_tolerance.insert(0, "30")
        row += 1

        self.lbl_pixel_info = ctk.CTkLabel(content, text="No pixel watch set",
            font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_pixel_info.grid(row=row, column=0, columnspan=4, padx=15, pady=(0, 5), sticky="w")
        row += 1

        # ====== SOUND ALERTS ======
        lbl = ctk.CTkLabel(content, text="Sound Alerts",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Audio beeps for break start/end, stop events, and alerts.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        self.var_sound_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(content, text="Enable sound alerts (break/stop)",
            variable=self.var_sound_enabled).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        # ====== VISUAL OVERLAY ======
        self.var_overlay_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(content, text="Show region overlay on screen",
            variable=self.var_overlay_enabled,
            command=self._toggle_overlay).grid(row=row, column=0, columnspan=4, padx=15, pady=2, sticky="w")
        row += 1

        # ====== SESSION LOG ======
        lbl = ctk.CTkLabel(content, text="Session Log",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Record every click with timestamp, position, interval, and type. Export to CSV.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        log_frm = ctk.CTkFrame(content, fg_color="transparent")
        log_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        self.var_log_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(log_frm, text="Log clicks",
            variable=self.var_log_enabled).pack(side="left", padx=2)
        ctk.CTkButton(log_frm, text="Export CSV", width=80, height=28,
            command=self._export_log, fg_color="#00b894", hover_color="#00a381").pack(side="left", padx=8)
        row += 1

        # ====== HOTKEY CONFIGURATION ======
        lbl = ctk.CTkLabel(content, text="Start/Stop Hotkey",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Change the hotkey. Click Record, then press any key or mouse button.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        hotkey_frm = ctk.CTkFrame(content, fg_color="transparent")
        hotkey_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        self.lbl_hotkey = ctk.CTkLabel(hotkey_frm, text="Current: F6",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#00cec9")
        self.lbl_hotkey.pack(side="left", padx=(5, 12))
        self.btn_record_hotkey = ctk.CTkButton(hotkey_frm, text="Record New Hotkey",
            command=self._record_hotkey, height=28, font=ctk.CTkFont(size=11),
            fg_color="#0984e3", hover_color="#0769b5")
        self.btn_record_hotkey.pack(side="left", padx=2)
        row += 1

        # ====== APPEARANCE ======
        lbl = ctk.CTkLabel(content, text="Appearance",
                           font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        row += 1

        ctk.CTkLabel(content, text="Switch between Dark, Light, or System-default theme.",
            font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, columnspan=4, padx=15, pady=(0, 3), sticky="w")
        row += 1

        appear_frm = ctk.CTkFrame(content, fg_color="transparent")
        appear_frm.grid(row=row, column=0, columnspan=4, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(appear_frm, text="Theme:").pack(side="left", padx=(0, 3))
        self.theme_menu = ctk.CTkOptionMenu(appear_frm, values=["Dark", "Light", "System"],
                                             command=self._change_theme)
        self.theme_menu.set("Dark")
        self.theme_menu.pack(side="left", padx=3)
        ctk.CTkButton(appear_frm, text="Mini Mode", width=80, height=28,
            command=self._enter_mini_mode, fg_color="#636e72", hover_color="#535c60").pack(side="left", padx=12)
        row += 1


        # --- Controls (fixed at bottom) ---
        ctrl_frm = ctk.CTkFrame(self)
        ctrl_frm.grid(row=3, column=0, padx=12, pady=(3, 5), sticky="ew")
        ctrl_frm.grid_columnconfigure(2, weight=1)

        self.btn_toggle = ctk.CTkButton(ctrl_frm, text="Start (F6)", command=self.toggle,
                                         height=38, font=ctk.CTkFont(size=14, weight="bold"),
                                         fg_color="#28a745", hover_color="#218838")
        self.btn_toggle.grid(row=0, column=0, padx=8, pady=8)

        self.lbl_status = ctk.CTkLabel(ctrl_frm, text="  STOPPED  ",
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color="#ff4444", corner_radius=8)
        self.lbl_status.grid(row=0, column=1, padx=6, pady=8)

        self.lbl_clicks = ctk.CTkLabel(ctrl_frm, text="Clicks: 0",
                                        font=ctk.CTkFont(size=12))
        self.lbl_clicks.grid(row=0, column=2, padx=6, pady=8)

        self.lbl_timer = ctk.CTkLabel(ctrl_frm, text="",
                                       font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_timer.grid(row=0, column=3, padx=6, pady=8)

        # Footer
        self.lbl_footer = ctk.CTkLabel(self, text="F6 = Start/Stop  |  ESC = Emergency Stop",
                              font=ctk.CTkFont(size=10), text_color="gray")
        self.lbl_footer.grid(row=4, column=0, padx=20, pady=(0, 8))


    # ----- Helpers -----

    def _get_float(self, entry, default=1.0):
        try:
            return float(entry.get())
        except (ValueError, TypeError):
            return default

    def _get_int(self, entry, default=50):
        try:
            return int(entry.get())
        except (ValueError, TypeError):
            return default

    # ----- Basic Callbacks -----

    def _on_click_type(self, value):
        self.var_click_type.set(value.lower())

    def _change_theme(self, value):
        ctk.set_appearance_mode(value.lower())

    def _toggle_area(self):
        mode = self.var_target_mode.get()
        area_on = mode == "area"
        for e in self.area_entries.values():
            e.configure(state="normal" if area_on else "disabled")
        prayer_on = mode == "prayer"
        self.prayer_speed_menu.configure(state="normal" if prayer_on else "disabled")

    def _update_hotkey_display(self):
        name = self._hotkey_name
        self.lbl_hotkey.configure(text="Current: {}".format(name))
        if self.running:
            self.btn_toggle.configure(text="Stop ({})".format(name))
        else:
            self.btn_toggle.configure(text="Start ({})".format(name))
        self.lbl_footer.configure(text="{} = Start/Stop  |  ESC = Emergency Stop".format(name))

    def _update_status(self, text, color):
        self.lbl_status.configure(text="  {}  ".format(text), text_color=color)

    def _update_clicks(self):
        self.lbl_clicks.configure(text="Clicks: {}".format(self.click_count))

    def _show_help(self):
        win = ctk.CTkToplevel(self)
        win.title("Help - Smarter Auto Clicker v3")
        win.geometry("520x520")
        win.transient(self)
        win.grab_set()
        win.attributes("-topmost", True)
        txt = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=11), wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        txt.insert("1.0", HELP_TEXT)
        txt.configure(state="disabled")
        ctk.CTkButton(win, text="Close", command=win.destroy,
            height=32, fg_color="#636e72", hover_color="#535c60").pack(pady=(5, 10))

    def _play_sound(self, kind):
        if not self.var_sound_enabled.get():
            return
        def beep():
            try:
                if kind == "break_start":
                    winsound.Beep(400, 200)
                elif kind == "break_end":
                    winsound.Beep(800, 200)
                elif kind == "stopped":
                    winsound.Beep(600, 150)
                    time.sleep(0.1)
                    winsound.Beep(400, 200)
                elif kind == "alert":
                    for _ in range(3):
                        winsound.Beep(1000, 100)
                        time.sleep(0.05)
            except Exception:
                pass
        threading.Thread(target=beep, daemon=True).start()

    def _update_timer_display(self):
        if self._session_start is None or not self.running:
            return
        elapsed = time.perf_counter() - self._session_start
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        self.lbl_timer.configure(text="{}:{:02d}".format(mins, secs))
        self._timer_id = self.after(1000, self._update_timer_display)


    # ----- Profile Management -----

    def _get_profile_data(self):
        return {
            "min_interval": self.var_min_interval.get(),
            "max_interval": self.var_max_interval.get(),
            "click_type": self.var_click_type.get(),
            "target_mode": self.var_target_mode.get(),
            "area": {k: e.get() for k, e in self.area_entries.items()},
            "breaks_enabled": self.var_breaks_enabled.get(),
            "break_clicks_min": self.var_break_clicks_min.get(),
            "break_clicks_max": self.var_break_clicks_max.get(),
            "break_dur_min": self.var_break_dur_min.get(),
            "break_dur_max": self.var_break_dur_max.get(),
            "human_mouse": self.var_human_mouse.get(),
            "hw_clicks": self.var_hw_clicks.get(),
            "use_sendmsg": self.var_use_sendmsg.get(),
            "ramp_enabled": self.var_ramp_enabled.get(),
            "ramp_start": self.var_ramp_start.get(),
            "ramp_end": self.var_ramp_end.get(),
            "ramp_clicks": self.var_ramp_clicks.get(),
            "afk_enabled": self.var_afk_enabled.get(),
            "afk_interval": self.var_afk_interval.get(),
            "sound_enabled": self.var_sound_enabled.get(),
            "session_limit": self.var_session_limit.get(),
            "key_injections": self.key_injections[:],
            "click_zones": self.click_zones[:],
            "click_sequence": self.click_sequence[:],
        }

    def _apply_profile_data(self, data):
        def _set_entry(entry, val):
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, str(val))
        _set_entry(self.var_min_interval, data.get("min_interval", "0.8"))
        _set_entry(self.var_max_interval, data.get("max_interval", "2.5"))
        ct = data.get("click_type", "left")
        self.var_click_type.set(ct)
        self.click_type_seg.set(ct.capitalize())
        self.var_target_mode.set(data.get("target_mode", "cursor"))
        for k, v in data.get("area", {}).items():
            if k in self.area_entries:
                _set_entry(self.area_entries[k], v)
        self.var_breaks_enabled.set(data.get("breaks_enabled", True))
        _set_entry(self.var_break_clicks_min, data.get("break_clicks_min", "30"))
        _set_entry(self.var_break_clicks_max, data.get("break_clicks_max", "80"))
        _set_entry(self.var_break_dur_min, data.get("break_dur_min", "3.0"))
        _set_entry(self.var_break_dur_max, data.get("break_dur_max", "12.0"))
        self.var_human_mouse.set(data.get("human_mouse", True))
        self.var_hw_clicks.set(data.get("hw_clicks", False))
        self.var_use_sendmsg.set(data.get("use_sendmsg", False))
        self.var_ramp_enabled.set(data.get("ramp_enabled", False))
        _set_entry(self.var_ramp_start, data.get("ramp_start", "1.0"))
        _set_entry(self.var_ramp_end, data.get("ramp_end", "0.5"))
        _set_entry(self.var_ramp_clicks, data.get("ramp_clicks", "200"))
        self.var_afk_enabled.set(data.get("afk_enabled", False))
        _set_entry(self.var_afk_interval, data.get("afk_interval", "30"))
        self.var_sound_enabled.set(data.get("sound_enabled", False))
        _set_entry(self.var_session_limit, data.get("session_limit", ""))
        self.key_injections = data.get("key_injections", [])
        self._update_inject_info()
        self.click_zones = data.get("click_zones", [])
        self._update_zones_info()
        self.click_sequence = data.get("click_sequence", [])
        self._update_seq_info()
        self._toggle_area()

    def _save_profile(self):
        dialog = ctk.CTkInputDialog(text="Profile name:", title="Save Profile")
        name = dialog.get_input()
        if name and name.strip():
            name = name.strip()
            ProfileManager.save(name, self._get_profile_data())
            profiles = ProfileManager.list_profiles()
            self.profile_menu.configure(values=["(none)"] + profiles)
            self.profile_var.set(name)

    def _load_profile(self):
        name = self.profile_var.get()
        if name == "(none)":
            return
        try:
            data = ProfileManager.load(name)
            self._apply_profile_data(data)
        except Exception as e:
            print("[Profile] Load error: {}".format(e))

    def _delete_profile(self):
        name = self.profile_var.get()
        if name == "(none)":
            return
        ProfileManager.delete(name)
        profiles = ProfileManager.list_profiles()
        self.profile_menu.configure(values=["(none)"] + profiles)
        self.profile_var.set("(none)")

    # ----- Zone Management -----

    def _add_zone(self):
        self.iconify()
        time.sleep(0.3)
        def on_zone(x, y, w, h):
            self.click_zones.append((x, y, w, h, 1.0))
            self.after(0, self._update_zones_info)
            self.after(0, self.deiconify)
        def run_sel():
            selector = RegionSelector(on_zone)
            selector.run()
            if self.state() == "iconic":
                self.after(0, self.deiconify)
        threading.Thread(target=run_sel, daemon=True).start()

    def _clear_zones(self):
        self.click_zones = []
        self._update_zones_info()

    def _update_zones_info(self):
        if not self.click_zones:
            self.lbl_zones_info.configure(text="No zones defined", text_color="gray")
        else:
            parts = []
            for i, z in enumerate(self.click_zones):
                parts.append("Z{}: {}x{} at ({},{})".format(i + 1, z[2], z[3], z[0], z[1]))
            self.lbl_zones_info.configure(text="  ".join(parts), text_color="#00cc66")

    # ----- Sequence Management -----

    def _add_sequence_point(self):
        if len(self.click_sequence) >= 10:
            return
        self.iconify()
        time.sleep(0.3)
        def wait_click():
            picked = threading.Event()
            def on_click(x, y, button, pressed):
                if pressed:
                    self.click_sequence.append((int(x), int(y)))
                    self.after(0, self._update_seq_info)
                    self.after(0, self.deiconify)
                    picked.set()
                    return False
            listener = pynput_mouse.Listener(on_click=on_click)
            listener.start()
            picked.wait(timeout=15)
            if not picked.is_set():
                self.after(0, self.deiconify)
        threading.Thread(target=wait_click, daemon=True).start()

    def _clear_sequence(self):
        self.click_sequence = []
        self._seq_index = 0
        self._update_seq_info()

    def _update_seq_info(self):
        if not self.click_sequence:
            self.lbl_seq_info.configure(text="No sequence points", text_color="gray")
        else:
            pts = ["{}: ({},{})".format(i + 1, p[0], p[1]) for i, p in enumerate(self.click_sequence)]
            self.lbl_seq_info.configure(text="  ".join(pts), text_color="#00cc66")

    # ----- Prayer Flick Settings -----

    def _on_prayer_speed_change(self, choice):
        tick_map = {
            "2 ticks (1200ms)": 1200,
            "3 ticks (1800ms)": 1800,
            "4 ticks (2400ms)": 2400,
            "5 ticks (3000ms)": 3000,
            "6 ticks (3600ms)": 3600,
            "7 ticks (4200ms)": 4200,
        }
        self._prayer_interval = tick_map.get(choice, 3000)
        self.lbl_prayer_info.configure(
            text="Flick interval: {}ms  |  Press Start to begin flicking at cursor position.".format(
                self._prayer_interval))

    # ----- Key Injection Management -----

    def _add_key_injection(self):
        key = self.var_inject_key.get().strip()
        every = self.var_inject_every.get().strip()
        if key and every:
            try:
                n = int(every)
                if n > 0:
                    self.key_injections.append((key, n))
                    self._update_inject_info()
            except ValueError:
                pass

    def _clear_key_injections(self):
        self.key_injections = []
        self._update_inject_info()

    def _update_inject_info(self):
        if not self.key_injections:
            self.lbl_inject_info.configure(text="No key injections", text_color="gray")
        else:
            parts = ["{} every {} clicks".format(k, n) for k, n in self.key_injections]
            self.lbl_inject_info.configure(text="  |  ".join(parts), text_color="#00cc66")

    # ----- Pixel Watch -----

    def _pick_pixel(self):
        self.iconify()
        time.sleep(0.3)
        def wait_click():
            picked = threading.Event()
            def on_click(x, y, button, pressed):
                if pressed:
                    ix, iy = int(x), int(y)
                    try:
                        img = ImageGrab.grab(bbox=(ix, iy, ix + 1, iy + 1))
                        r, g, b = img.getpixel((0, 0))[:3]
                        self._pixel_watch = (ix, iy, r, g, b)
                        self.after(0, lambda: self.lbl_pixel_info.configure(
                            text="Pixel ({},{}) RGB({},{},{})".format(ix, iy, r, g, b),
                            text_color="#00cc66"))
                    except Exception as e:
                        self.after(0, lambda: self.lbl_pixel_info.configure(
                            text="Capture failed: {}".format(e), text_color="#ff4444"))
                    self.after(0, self.deiconify)
                    picked.set()
                    return False
            listener = pynput_mouse.Listener(on_click=on_click)
            listener.start()
            picked.wait(timeout=15)
            if not picked.is_set():
                self.after(0, self.deiconify)
        threading.Thread(target=wait_click, daemon=True).start()

    def _clear_pixel(self):
        self._pixel_watch = None
        self.lbl_pixel_info.configure(text="No pixel watch set", text_color="gray")

    def _check_pixel(self):
        if self._pixel_watch is None:
            return False
        px, py, ref_r, ref_g, ref_b = self._pixel_watch
        tol = self._get_int(self.var_pixel_tolerance, 30)
        try:
            img = ImageGrab.grab(bbox=(px, py, px + 1, py + 1))
            r, g, b = img.getpixel((0, 0))[:3]
            diff = abs(r - ref_r) + abs(g - ref_g) + abs(b - ref_b)
            return diff > tol
        except Exception:
            return False

    # ----- Visual Overlay -----

    def _toggle_overlay(self):
        if self.var_overlay_enabled.get():
            region = self.selected_region
            if region:
                self.region_overlay.show(*region)
            else:
                self.var_overlay_enabled.set(False)
        else:
            self.region_overlay.hide()

    # ----- Export Log -----

    def _export_log(self):
        self.session_logger.enabled = self.var_log_enabled.get()
        path = self.session_logger.export()
        if path:
            print("[Log] Exported to: {}".format(path))
            self._update_status("LOG EXPORTED", "#00cc66")
        else:
            self._update_status("NO LOG DATA", "#ff9900")

    # ----- Mini Mode -----

    def _enter_mini_mode(self):
        if self._mini_win is not None:
            return
        self.withdraw()
        mini = ctk.CTkToplevel()
        mini.title("AutoClicker")
        mini.geometry("220x90")
        mini.resizable(False, False)
        mini.attributes("-topmost", True)
        mini.protocol("WM_DELETE_WINDOW", self._exit_mini_mode)
        self._mini_win = mini
        self._mini_status = ctk.CTkLabel(mini, text="STOPPED",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#ff4444")
        self._mini_status.pack(pady=(5, 2))
        self._mini_clicks = ctk.CTkLabel(mini, text="Clicks: 0",
            font=ctk.CTkFont(size=11))
        self._mini_clicks.pack()
        btn_frm = ctk.CTkFrame(mini, fg_color="transparent")
        btn_frm.pack(pady=3)
        ctk.CTkButton(btn_frm, text="Expand", width=70, height=26,
            command=self._exit_mini_mode, fg_color="#0984e3").pack(side="left", padx=3)
        hk = self._hotkey_name
        ctk.CTkLabel(mini, text="{} = toggle".format(hk),
            font=ctk.CTkFont(size=9), text_color="gray").pack()
        mini._drag_x = 0
        mini._drag_y = 0
        def start_drag(e):
            mini._drag_x = e.x
            mini._drag_y = e.y
        def do_drag(e):
            x = mini.winfo_x() + e.x - mini._drag_x
            y = mini.winfo_y() + e.y - mini._drag_y
            mini.geometry("+{}+{}".format(x, y))
        mini.bind("<Button-1>", start_drag)
        mini.bind("<B1-Motion>", do_drag)

    def _exit_mini_mode(self):
        if self._mini_win is not None:
            try:
                self._mini_win.destroy()
            except Exception:
                pass
            self._mini_win = None
        self.deiconify()

    def _update_mini(self):
        if self._mini_win is None:
            return
        try:
            if self.running:
                self._mini_status.configure(text="RUNNING", text_color="#00cc66")
            else:
                self._mini_status.configure(text="STOPPED", text_color="#ff4444")
            self._mini_clicks.configure(text="Clicks: {}".format(self.click_count))
        except Exception:
            pass


    # ----- Hotkey Recorder -----

    def _record_hotkey(self):
        if self._recording_hotkey:
            return
        self._recording_hotkey = True
        self.btn_record_hotkey.configure(text="Press any key...", fg_color="#ff9900")
        self.lbl_hotkey.configure(text_color="#ff9900")

    def _finish_recording_key(self, key):
        if not self._recording_hotkey:
            return
        if key == keyboard.Key.esc:
            self._recording_hotkey = False
            self.after(0, lambda: self.btn_record_hotkey.configure(text="Record New Hotkey", fg_color="#0984e3"))
            self.after(0, lambda: self.lbl_hotkey.configure(text_color="#00cec9"))
            self.after(0, self._update_hotkey_display)
            return
        self._hotkey = key
        self._hotkey_name = key_to_name(key)
        self._hotkey_is_mouse = False
        self._recording_hotkey = False
        self.after(0, lambda: self.btn_record_hotkey.configure(text="Record New Hotkey", fg_color="#0984e3"))
        self.after(0, lambda: self.lbl_hotkey.configure(text_color="#00cec9"))
        self.after(0, self._update_hotkey_display)
        self.after(0, self._restart_hotkey_listener)

    def _finish_recording_mouse(self, x, y, button, pressed):
        if not self._recording_hotkey or not pressed:
            return
        btn_str = str(button)
        if btn_str in ("Button.left", "Button.right"):
            return
        self._hotkey = button
        self._hotkey_name = mouse_button_to_name(button)
        self._hotkey_is_mouse = True
        self._recording_hotkey = False
        self.after(0, lambda: self.btn_record_hotkey.configure(text="Record New Hotkey", fg_color="#0984e3"))
        self.after(0, lambda: self.lbl_hotkey.configure(text_color="#00cec9"))
        self.after(0, self._update_hotkey_display)
        self.after(0, self._restart_hotkey_listener)

    # ----- Region Selector -----

    def _select_region(self):
        self.iconify()
        time.sleep(0.3)
        def on_region_selected(x, y, w, h):
            self.selected_region = (x, y, w, h)
            for key, val in [("X", x), ("Y", y), ("W", w), ("H", h)]:
                entry = self.area_entries[key]
                entry.configure(state="normal")
                entry.delete(0, "end")
                entry.insert(0, str(val))
                if self.var_target_mode.get() != "area":
                    entry.configure(state="disabled")
            self.lbl_region_info.configure(
                text="Region: {}x{} at ({}, {})".format(w, h, x, y),
                text_color="#00cc66")
            if self.var_overlay_enabled.get():
                self.region_overlay.show(x, y, w, h)
            self.deiconify()
        def run_selector():
            selector = RegionSelector(on_region_selected)
            selector.run()
            if self.selected_region is None or self.state() == "iconic":
                self.after(0, self.deiconify)
        threading.Thread(target=run_selector, daemon=True).start()

    # ----- Window Picker -----

    def _pick_window(self):
        self._picking_window = True
        self.lbl_region_info.configure(
            text="Click on the target window...",
            text_color="#fdcb6e")
        self.iconify()
        time.sleep(0.3)
        def wait_for_click():
            picked = threading.Event()
            def on_click(x, y, button, pressed):
                if pressed and self._picking_window:
                    self._picking_window = False
                    direct = user32.WindowFromPoint(ctypes.wintypes.POINT(int(x), int(y)))
                    root = user32.GetAncestor(direct, 2) or direct
                    self.target_hwnd = direct
                    self.target_root = root
                    title = get_window_title(root)
                    short = title[:37] + ".." if len(title) > 40 else title
                    # Get client rect for info
                    r = ctypes.wintypes.RECT()
                    user32.GetClientRect(direct, ctypes.byref(r))
                    info = "Window: {} ({}x{})".format(short, r.right, r.bottom)
                    if direct != root:
                        info += " [child]"
                    print("[Pick] direct={} root={} title={}".format(direct, root, title[:50]))
                    self.after(0, lambda: self.lbl_region_info.configure(
                        text=info, text_color="#00cc66"))
                    self.after(0, lambda: self.var_target_mode.set("background"))
                    self.after(0, self.deiconify)
                    picked.set()
                    return False
            listener = pynput_mouse.Listener(on_click=on_click)
            listener.start()
            picked.wait(timeout=30)
            if not picked.is_set():
                self._picking_window = False
                self.after(0, lambda: self.lbl_region_info.configure(
                    text="Window pick timed out", text_color="#ff4444"))
                self.after(0, self.deiconify)
        threading.Thread(target=wait_for_click, daemon=True).start()

    def _test_bg_click(self):
        hwnd = self.target_hwnd
        if hwnd is None:
            self.lbl_region_info.configure(text="No window picked!", text_color="#ff4444")
            return
        if not user32.IsWindow(hwnd):
            self.lbl_region_info.configure(text="Window no longer valid!", text_color="#ff4444")
            return
        # Use region center if region selected, else window center
        region = self.selected_region
        if region is not None:
            rx, ry, rw, rh = region
            cx, cy = screen_to_client(hwnd, rx + rw // 2, ry + rh // 2)
        else:
            r = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            cx, cy = r.right // 2, r.bottom // 2
        lp = _make_lparam(cx, cy)
        # PostMessage to direct child - matches what auto-clicker uses
        _bg_post(hwnd, WM_MOUSEMOVE, 0, lp, False)
        time.sleep(0.02)
        r1 = _bg_post(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp, False)
        time.sleep(0.05)
        r2 = _bg_post(hwnd, WM_LBUTTONUP, 0, lp, False)
        cls = get_window_class(hwnd)
        root = getattr(self, 'target_root', hwnd) or hwnd
        title = get_window_title(root)
        result = "OK" if (r1 and r2) else "r1={} r2={}".format(r1, r2)
        msg = "Test: PostMsg ({},{}) -> {} [{}]".format(cx, cy, result, title[:25])
        self.lbl_region_info.configure(text=msg, text_color="#00cc66" if (r1 and r2) else "#ff4444")
        print("[Test] PostMsg hwnd={}({}) click=({},{}) r1={} r2={} [{}]".format(
            hwnd, cls[:15], cx, cy, r1, r2, title[:30]))

    def _clear_region(self):
        self.selected_region = None
        self.target_hwnd = None
        self.target_root = None
        self.lbl_region_info.configure(
            text="No region/window selected",
            text_color="gray")
        self.region_overlay.hide()
        self.var_overlay_enabled.set(False)


    # ----- Global Hotkey Listener -----

    def _start_hotkey_listener(self):
        def on_kb_press(key):
            try:
                if self._recording_hotkey:
                    self._finish_recording_key(key)
                    return
                if not self._hotkey_is_mouse:
                    if key == self._hotkey:
                        self.after(0, self.toggle)
                if key == keyboard.Key.esc:
                    self.after(0, self.emergency_stop)
            except Exception:
                pass

        def on_mouse_click(x, y, button, pressed):
            try:
                if self._recording_hotkey and pressed:
                    self._finish_recording_mouse(x, y, button, pressed)
                    return
                if self._hotkey_is_mouse and pressed:
                    if str(button) == str(self._hotkey):
                        self.after(0, self.toggle)
            except Exception:
                pass

        self._kb_listener = keyboard.Listener(on_press=on_kb_press, daemon=True)
        self._kb_listener.start()
        self._mouse_listener = pynput_mouse.Listener(on_click=on_mouse_click, daemon=True)
        self._mouse_listener.start()

    def _restart_hotkey_listener(self):
        if self._kb_listener:
            self._kb_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        self._start_hotkey_listener()

    # ----- Start / Stop -----

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.running:
            return
        mode = self.var_target_mode.get()
        if mode == "background" and self.target_hwnd is None:
            self._update_status("NO WINDOW!", "#ff4444")
            return
        if mode == "sequence" and not self.click_sequence:
            self._update_status("NO SEQUENCE!", "#ff4444")
            return
        if mode == "zones" and not self.click_zones:
            self._update_status("NO ZONES!", "#ff4444")
            return
        self.running = True
        self.stop_event.clear()
        self.click_count = 0
        self._seq_index = 0
        self._session_start = time.perf_counter()
        self.session_logger.enabled = self.var_log_enabled.get()
        self.session_logger.clear()
        self._update_status("RUNNING", "#00cc66")
        self._update_mini()
        hk = self._hotkey_name
        self.btn_toggle.configure(text="Stop ({})".format(hk), fg_color="#dc3545", hover_color="#c82333")
        self._update_timer_display()
        self.worker_thread = threading.Thread(target=self._click_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        self.stop_event.set()
        self._session_start = None
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        self.lbl_timer.configure(text="")
        self._update_status("STOPPED", "#ff4444")
        self._play_sound("stopped")
        self._update_mini()
        hk = self._hotkey_name
        self.btn_toggle.configure(text="Start ({})".format(hk), fg_color="#28a745", hover_color="#218838")

    def emergency_stop(self):
        self.stop()
        self._update_status("EMERGENCY STOP", "#ff4444")
        self._play_sound("alert")


    # ----- Click Loop (runs in worker thread) -----

    def _click_loop(self):
        next_break_at = self._next_break_count()
        last_afk_time = time.perf_counter()

        while not self.stop_event.is_set():
            try:
                # --- Session timer auto-stop ---
                session_limit_str = self.var_session_limit.get().strip()
                if session_limit_str:
                    try:
                        limit_min = float(session_limit_str)
                        if limit_min > 0 and self._session_start is not None:
                            elapsed = time.perf_counter() - self._session_start
                            if elapsed >= limit_min * 60:
                                self._play_sound("alert")
                                self.after(0, lambda: self._update_status("TIME LIMIT", "#ff9900"))
                                self.after(0, self.stop)
                                return
                    except ValueError:
                        pass

                # --- Pixel watch conditional stop ---
                if self._check_pixel():
                    self._play_sound("alert")
                    self.after(0, lambda: self._update_status("PIXEL CHANGED", "#ff9900"))
                    self.after(0, self.stop)
                    return

                # --- Break check ---
                if self.var_breaks_enabled.get() and self.click_count >= next_break_at:
                    self._take_break()
                    next_break_at = self.click_count + self._next_break_count()

                # --- Anti-AFK jitter ---
                if self.var_afk_enabled.get():
                    afk_interval = self._get_float(self.var_afk_interval, 30.0)
                    if time.perf_counter() - last_afk_time >= afk_interval:
                        last_afk_time = time.perf_counter()
                        if self.var_target_mode.get() != "background":
                            cx, cy = pyautogui.position()
                            jx = cx + random.randint(-20, 20)
                            jy = cy + random.randint(-15, 15)
                            human_move(jx, jy, (0.05, 0.15))

                mode = self.var_target_mode.get()
                ct = self.var_click_type.get()

                # === Determine click position and perform click ===

                if mode == "background":
                    hwnd = self.target_hwnd
                    if hwnd is None or not user32.IsWindow(hwnd):
                        self.after(0, lambda: self._update_status("WINDOW LOST", "#ff4444"))
                        self.after(0, self.stop)
                        return
                    region = self.selected_region
                    cx, cy = get_bg_click_position(hwnd, region)
                    cx = max(0, int(cx + random.gauss(0, 2)))
                    cy = max(0, int(cy + random.gauss(0, 2)))
                    if self.stop_event.is_set():
                        break
                    use_hw = self.var_hw_clicks.get()
                    use_send = self.var_use_sendmsg.get()
                    root = getattr(self, "target_root", hwnd) or hwnd
                    if use_hw:
                        if ct == "left":
                            hw_click_left(hwnd, cx, cy)
                        elif ct == "right":
                            hw_click_right(hwnd, cx, cy)
                        elif ct == "double":
                            hw_click_double(hwnd, cx, cy)
                    else:
                        if ct == "left":
                            r1, r2 = bg_click_left(hwnd, cx, cy, False)
                        elif ct == "right":
                            r1, r2 = bg_click_right(hwnd, cx, cy, False)
                        elif ct == "double":
                            bg_click_double(hwnd, cx, cy, False)
                    if self.var_bg_debug.get():
                        method = "HW" if use_hw else "PostMsg"
                        title = get_window_title(root)
                        cls_d = get_window_class(hwnd)
                        r_d = ctypes.wintypes.RECT()
                        user32.GetClientRect(hwnd, ctypes.byref(r_d))
                        print("[BG] {} hwnd={}({}) ({}x{}) pos=({},{}) [{}]".format(
                            method, hwnd, cls_d[:15], r_d.right, r_d.bottom, cx, cy, title[:25]))
                    click_x, click_y = cx, cy


                elif mode == "sequence":
                    if not self.click_sequence:
                        self.after(0, self.stop)
                        return
                    tx, ty = self.click_sequence[self._seq_index % len(self.click_sequence)]
                    self._seq_index += 1
                    tx += random.randint(-2, 2)
                    ty += random.randint(-2, 2)
                    if self.var_human_mouse.get():
                        human_move(tx, ty)
                    else:
                        pyautogui.moveTo(tx, ty, _pause=False)
                    if self.stop_event.is_set():
                        break
                    if ct == "left":
                        pyautogui.click(tx, ty, _pause=False)
                    elif ct == "right":
                        pyautogui.rightClick(tx, ty, _pause=False)
                    elif ct == "double":
                        pyautogui.doubleClick(tx, ty, _pause=False)
                    click_x, click_y = tx, ty

                elif mode == "zones":
                    if not self.click_zones:
                        self.after(0, self.stop)
                        return
                    weights = [z[4] for z in self.click_zones]
                    total = sum(weights)
                    r = random.uniform(0, total)
                    cum = 0
                    zone = self.click_zones[0]
                    for z in self.click_zones:
                        cum += z[4]
                        if r <= cum:
                            zone = z
                            break
                    zx, zy, zw, zh = zone[0], zone[1], zone[2], zone[3]
                    tx = int(random.gauss(zx + zw / 2, zw / 6))
                    ty = int(random.gauss(zy + zh / 2, zh / 6))
                    tx = max(zx, min(zx + zw, tx))
                    ty = max(zy, min(zy + zh, ty))
                    if self.var_human_mouse.get():
                        human_move(tx, ty)
                    else:
                        pyautogui.moveTo(tx, ty, _pause=False)
                    if self.stop_event.is_set():
                        break
                    if ct == "left":
                        pyautogui.click(tx, ty, _pause=False)
                    elif ct == "right":
                        pyautogui.rightClick(tx, ty, _pause=False)
                    elif ct == "double":
                        pyautogui.doubleClick(tx, ty, _pause=False)
                    click_x, click_y = tx, ty


                elif mode == "prayer":
                    # ----- 1-TICK PRAYER FLICK MODE -----
                    # Two rapid clicks with randomized ~600-625ms gaps,
                    # then wait the remainder of the monster's attack interval.
                    sleep1 = random.randint(600, 625) / 1000.0
                    sleep2 = random.randint(600, 625) / 1000.0
                    interval_sec = self._prayer_interval / 1000.0
                    remainder = max(0, interval_sec - (sleep1 + sleep2))

                    # First click (prayer on)
                    click_x, click_y = pyautogui.position()
                    pyautogui.click(click_x, click_y, _pause=False)
                    self.click_count += 1
                    self.after(0, self._update_clicks)

                    # Wait sleep1
                    end1 = time.perf_counter() + sleep1
                    while time.perf_counter() < end1:
                        if self.stop_event.is_set():
                            return
                        time.sleep(0.01)

                    # Second click (prayer off)
                    pyautogui.click(click_x, click_y, _pause=False)

                    # Wait sleep2
                    end2 = time.perf_counter() + sleep2
                    while time.perf_counter() < end2:
                        if self.stop_event.is_set():
                            return
                        time.sleep(0.01)

                    # Wait remainder of attack interval
                    end3 = time.perf_counter() + remainder
                    while time.perf_counter() < end3:
                        if self.stop_event.is_set():
                            return
                        time.sleep(0.01)

                    # Session logging
                    self.session_logger.log(click_x, click_y, interval_sec, "left", mode)
                    self.after(0, self._update_mini)
                    continue

                else:
                    # ----- CURSOR / AREA MODE -----
                    area = None
                    if mode == "area":
                        area = (self._get_int(self.area_entries["X"], 100),
                                self._get_int(self.area_entries["Y"], 100),
                                self._get_int(self.area_entries["W"], 300),
                                self._get_int(self.area_entries["H"], 300))
                    tx, ty = get_click_position(mode, area)
                    region = self.selected_region
                    if region is not None:
                        rx, ry, rw, rh = region
                        tx = max(rx, min(rx + rw, tx))
                        ty = max(ry, min(ry + rh, ty))
                    if self.var_human_mouse.get() and mode == "area":
                        human_move(tx, ty)
                    elif mode == "area":
                        pyautogui.moveTo(tx, ty, _pause=False)
                    if self.stop_event.is_set():
                        break
                    if region is not None:
                        cur_x, cur_y = pyautogui.position()
                        rx, ry, rw, rh = region
                        click_x = max(rx, min(rx + rw, cur_x))
                        click_y = max(ry, min(ry + rh, cur_y))
                    else:
                        click_x, click_y = tx, ty
                    if ct == "left":
                        pyautogui.click(click_x, click_y, _pause=False)
                    elif ct == "right":
                        pyautogui.rightClick(click_x, click_y, _pause=False)
                    elif ct == "double":
                        pyautogui.doubleClick(click_x, click_y, _pause=False)

                self.click_count += 1
                self.after(0, self._update_clicks)
                self.after(0, self._update_mini)

                # --- Keyboard injection ---
                for inj_key, inj_every in self.key_injections:
                    if self.click_count % inj_every == 0:
                        try:
                            pyautogui.press(inj_key, _pause=False)
                        except Exception:
                            pass

                # --- Calculate interval with speed ramping ---
                base_min = self._get_float(self.var_min_interval, 0.8)
                base_max = self._get_float(self.var_max_interval, 2.5)
                interval = random_interval(base_min, base_max)

                if self.var_ramp_enabled.get():
                    ramp_start = self._get_float(self.var_ramp_start, 1.0)
                    ramp_end = self._get_float(self.var_ramp_end, 0.5)
                    ramp_clicks = self._get_int(self.var_ramp_clicks, 200)
                    if ramp_clicks > 0:
                        progress = min(1.0, self.click_count / ramp_clicks)
                        multiplier = ramp_start + (ramp_end - ramp_start) * progress
                        interval *= multiplier

                # --- Session logging ---
                self.session_logger.log(click_x, click_y, interval, ct, mode)

                # --- Wait for interval ---
                end_time = time.perf_counter() + interval
                while time.perf_counter() < end_time:
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.05)

            except Exception as e:
                print("[AutoClicker] Error: {}".format(e))
                self.after(0, self.stop)
                return


    def _next_break_count(self):
        lo = self._get_int(self.var_break_clicks_min, 30)
        hi = self._get_int(self.var_break_clicks_max, 80)
        if lo > hi:
            lo, hi = hi, lo
        return random.randint(lo, hi)

    def _take_break(self):
        dur_min = self._get_float(self.var_break_dur_min, 3.0)
        dur_max = self._get_float(self.var_break_dur_max, 12.0)
        dur = random.uniform(dur_min, dur_max)
        self._play_sound("break_start")
        self.after(0, lambda: self._update_status("BREAK ({:.1f}s)".format(dur), "#ff9900"))
        end_time = time.perf_counter() + dur
        while time.perf_counter() < end_time:
            if self.stop_event.is_set():
                return
            if self.var_target_mode.get() != "background" and random.random() < 0.3:
                cx, cy = pyautogui.position()
                human_move(cx + random.randint(-15, 15), cy + random.randint(-10, 10), (0.1, 0.3))
            time.sleep(min(1.0, max(0.05, end_time - time.perf_counter())))
        self._play_sound("break_end")
        self.after(0, lambda: self._update_status("RUNNING", "#00cc66"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = AutoClickerApp()
    app.mainloop()


if __name__ == "__main__":
    main()

