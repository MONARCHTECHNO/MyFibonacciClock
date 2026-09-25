# Fibonacci Clock for Raspberry Pi Pico W (MicroPython)
# Inspired by: https://nerdcave.xyz/docs/projects/fibonnaci-clock/
# Improvements by Marcial:
#   - Startup Wi-Fi connection animation (color sweep) with timeout
#   - Real-time brightness control via two buttons (with hold-to-repeat)
#   - Config loaded from config.json first, with validated defaults as fallback
#   - Random choice between equivalent patterns (like the original clock)
#   - Periodic NTP re-sync + visual warning while time is not synced
#   - Night dimming, gamma-corrected brightness, brightness remembered after reboot
#   - Optional watchdog for 24/7 reliability

import machine
import time
import ujson
import neopixel
import random

try:
    import network
    import ntptime
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"   # remembers brightness between reboots

# Colors
RED    = (255, 0,   0)
GREEN  = (0,   255, 0)
BLUE   = (0,   0,   255)
BLACK  = (0,   0,   0)
YELLOW = (255, 255, 0)      # WiFi timeout / time-not-synced warning

DEFAULT_CONFIG = {
    "wifi_ssid": "Jade DR",
    "wifi_password": "13918158404",
    "timezone_offset_hours": 8,
    "ntp_host": "ntp.aliyun.com",
    "ntp_resync_hours": 6,

    "layout_led_counts": [16, 4, 2, 1, 1],
    "segment_order": [5, 3, 2, 1, 1],
    "pins": [1, 2, 3, 5, 4],
    "button_down_pin": 6,
    "button_up_pin": 7,

    "brightness": 0.8,
    "min_brightness": 0.1,
    "brightness_step": 0.1,
    "gamma": 2.2,               # 1.0 = no gamma correction

    "night_mode": False,
    "night_start_hour": 23,
    "night_end_hour": 7,
    "night_brightness": 0.2,

    "random_patterns": True,

    "enable_startup_animation": True,
    "startup_colors": [[255, 0, 0], [0, 255, 0], [0, 0, 255]],
    "startup_timeout_seconds": 60,

    "enable_watchdog": True,   # turn on once you're done debugging with Thonny
}

# -------------------- Watchdog-aware sleep --------------------
_wdt = None

def feed():
    if _wdt:
        _wdt.feed()

def sleep_ms(ms):
    """Sleep in small chunks so the watchdog keeps getting fed."""
    while ms > 0:
        feed()
        chunk = min(ms, 100)
        time.sleep_ms(chunk)
        ms -= chunk

# -------------------- Utilities --------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _coerce(cfg, key, fn):
    try:
        cfg[key] = fn(cfg[key])
    except Exception:
        print("Bad value for '{}', using default".format(key))
        cfg[key] = DEFAULT_CONFIG[key]

def _valid_color(c):
    return isinstance(c, (list, tuple)) and len(c) == 3 and all(isinstance(x, int) for x in c)

def load_config():
    cfg = dict(DEFAULT_CONFIG)

    # 1) Try config.json first
    try:
        with open(CONFIG_FILE, "r") as f:
            user = ujson.load(f)
        if not isinstance(user, dict):
            raise ValueError("top level must be an object")
        for k, v in user.items():
            if k in cfg:
                cfg[k] = v
            else:
                print("Unknown config key ignored:", k)
        print("Config loaded from", CONFIG_FILE)
    except OSError:
        print("No config.json found, using defaults")
    except ValueError as e:
        print("config.json invalid ({}), using defaults".format(e))

    # 2) Type checks (one bad value only resets that key, not the whole config)
    for k in ("timezone_offset_hours", "ntp_resync_hours", "brightness", "min_brightness",
              "brightness_step", "gamma", "night_brightness"):
        _coerce(cfg, k, float)
    for k in ("startup_timeout_seconds", "night_start_hour", "night_end_hour",
              "button_down_pin", "button_up_pin"):
        _coerce(cfg, k, int)
    for k in ("night_mode", "random_patterns", "enable_startup_animation", "enable_watchdog"):
        _coerce(cfg, k, bool)
    for k in ("wifi_ssid", "wifi_password", "ntp_host"):
        _coerce(cfg, k, str)

    # 3) Layout: all three lists must have the same length
    n = len(cfg["pins"]) if isinstance(cfg["pins"], list) else -1
    if not (n > 0 and isinstance(cfg["layout_led_counts"], list) and isinstance(cfg["segment_order"], list)
            and len(cfg["layout_led_counts"]) == n and len(cfg["segment_order"]) == n):
        print("pins / layout_led_counts / segment_order mismatch, using default layout")
        for k in ("pins", "layout_led_counts", "segment_order"):
            cfg[k] = DEFAULT_CONFIG[k]

    colors = cfg["startup_colors"]
    if not (isinstance(colors, list) and colors and all(_valid_color(c) for c in colors)):
        print("Bad startup_colors, using default")
        colors = DEFAULT_CONFIG["startup_colors"]
    cfg["startup_colors"] = [tuple(c) for c in colors]

    # 4) Clamps
    cfg["brightness_step"] = clamp(cfg["brightness_step"], 0.01, 0.5)
    cfg["min_brightness"] = clamp(cfg["min_brightness"], 0.01, 1.0)
    cfg["brightness"] = clamp(cfg["brightness"], cfg["min_brightness"], 1.0)
    cfg["night_brightness"] = clamp(cfg["night_brightness"], 0.01, 1.0)
    cfg["gamma"] = clamp(cfg["gamma"], 1.0, 3.0)
    cfg["ntp_resync_hours"] = clamp(cfg["ntp_resync_hours"], 0.5, 72)
    cfg["startup_timeout_seconds"] = clamp(cfg["startup_timeout_seconds"], 5, 300)
    return cfg

def load_saved_brightness():
    try:
        with open(STATE_FILE, "r") as f:
            return float(ujson.load(f)["brightness"])
    except Exception:
        return None

def save_brightness(b):
    try:
        with open(STATE_FILE, "w") as f:
            ujson.dump({"brightness": b}, f)
        print("Brightness saved:", b)
    except Exception as e:
        print("Could not save brightness:", e)

# -------------------- Fibonacci logic --------------------
def build_patterns(values):
    """For every reachable sum, list every set of squares (bitmask) that makes it."""
    n = len(values)
    table = {}
    for mask in range(1 << n):
        s = sum(values[i] for i in range(n) if (mask >> i) & 1)
        table.setdefault(s, []).append(mask)
    missing = [h for h in range(1, 13) if h not in table]
    if missing:
        print("WARNING: segment_order cannot show these values:", missing)
    return table

def pick_mask(table, target, randomize):
    options = table.get(target)
    if not options:
        return 0
    if randomize:
        return options[random.getrandbits(8) % len(options)]
    return options[0]

def compute_colors(table, n, h12, m5, randomize):
    hmask = pick_mask(table, h12, randomize)
    mmask = pick_mask(table, m5, randomize)
    colors = []
    for i in range(n):
        in_h = (hmask >> i) & 1
        in_m = (mmask >> i) & 1
        if in_h and in_m:
            colors.append(GREEN)
        elif in_h:
            colors.append(RED)
        elif in_m:
            colors.append(BLUE)
        else:
            colors.append(BLACK)
    return colors

# -------------------- Hardware --------------------
class Segments:
    """One NeoPixel strip per square, each on its own data pin."""

    def __init__(self, pins, led_counts, gamma):
        self.counts = led_counts
        self.n = len(pins)
        self.gamma = gamma
        self.brightness = 1.0
        self.colors = [BLACK] * self.n
        self.strips = [neopixel.NeoPixel(machine.Pin(p, machine.Pin.OUT), c)
                       for p, c in zip(pins, led_counts)]

    def _scale(self, color):
        f = self.brightness ** self.gamma
        # keep a lit channel at least 1 so very low brightness never looks "off"
        return tuple(0 if x == 0 else max(1, int(x * f + 0.5)) for x in color)

    def set(self, idx, color):
        self.colors[idx] = color

    def set_all(self, color):
        for i in range(self.n):
            self.colors[i] = color

    def show(self):
        for strip, color in zip(self.strips, self.colors):
            strip.fill(self._scale(color))
            strip.write()

    def clear(self):
        self.set_all(BLACK)
        self.show()

    def flash(self, color, ms):
        saved = list(self.colors)
        self.set_all(color)
        self.show()
        sleep_ms(ms)
        self.colors = saved
        self.show()

class Button:
    """Active-low button with debounce and hold-to-repeat."""

    DEBOUNCE_MS = 150
    HOLD_DELAY_MS = 600
    REPEAT_MS = 200

    def __init__(self, pin_no):
        self.pin = machine.Pin(pin_no, machine.Pin.IN, machine.Pin.PULL_UP)
        self.last = 1
        self.t_press = time.ticks_ms()
        self.t_repeat = self.t_press

    def fired(self, now):
        v = self.pin.value()
        hit = False
        if v == 0 and self.last == 1 and time.ticks_diff(now, self.t_press) > self.DEBOUNCE_MS:
            hit = True
            self.t_press = self.t_repeat = now
        elif (v == 0 and time.ticks_diff(now, self.t_press) > self.HOLD_DELAY_MS
              and time.ticks_diff(now, self.t_repeat) > self.REPEAT_MS):
            hit = True
            self.t_repeat = now
        self.last = v
        return hit

# -------------------- WiFi and Time --------------------
_wlan = None

def wifi_start(cfg):
    """Start connecting (non-blocking). Returns False if WiFi can't be used at all."""
    global _wlan
    if not WIFI_AVAILABLE or not cfg["wifi_ssid"]:
        return False
    if _wlan is None:
        _wlan = network.WLAN(network.STA_IF)
    _wlan.active(True)
    if not _wlan.isconnected():
        _wlan.connect(cfg["wifi_ssid"], cfg["wifi_password"])
    return True

def wifi_connected():
    return _wlan is not None and _wlan.isconnected()

def wifi_wait(timeout_s):
    t0 = time.ticks_ms()
    while not wifi_connected():
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
            return False
        sleep_ms(200)
    return True

def sync_time(cfg, retries=3):
    if not wifi_connected():
        return False
    ntptime.host = cfg["ntp_host"]
    for attempt in range(retries):
        feed()
        try:
            ntptime.settime()
            print("Time synced on attempt", attempt + 1)
            return True
        except Exception as e:
            print("NTP attempt {} failed: {}".format(attempt + 1, e))
            sleep_ms(2000)
    print("NTP sync failed after retries")
    return False

def get_local_time(tz_hours):
    return time.gmtime(time.time() + int(tz_hours * 3600))

def effective_brightness(user_b, hour, cfg):
    if not cfg["night_mode"]:
        return user_b
    start, end = cfg["night_start_hour"], cfg["night_end_hour"]
    if start > end:
        night = hour >= start or hour < end     # e.g. 23 -> 7
    else:
        night = start <= hour < end             # e.g. 1 -> 6
    return min(user_b, cfg["night_brightness"]) if night else user_b

# -------------------- Startup Animation --------------------
def startup(segments, cfg):
    """Connect WiFi while playing the color sweep. Returns True if connected."""
    can_connect = wifi_start(cfg)
    if not can_connect:
        print("WiFi not configured/available -> offline mode")

    if not cfg["enable_startup_animation"]:
        return wifi_wait(cfg["startup_timeout_seconds"]) if can_connect else False

    print("Starting WiFi connection animation...")
    t0 = time.ticks_ms()
    timeout = cfg["startup_timeout_seconds"] * 1000

    while True:
        for color in cfg["startup_colors"]:
            for idx in range(segments.n):
                if wifi_connected():
                    print("WiFi connected:", _wlan.ifconfig()[0])
                    segments.clear()
                    return True
                if can_connect and time.ticks_diff(time.ticks_ms(), t0) > timeout:
                    return _startup_failed(segments)
                segments.set(idx, color)
                segments.show()
                sleep_ms(150)
            sleep_ms(300)
        if not can_connect:
            # No WiFi configured: play the sweep once, then go offline
            return _startup_failed(segments)

def _startup_failed(segments):
    print("WiFi unavailable -> yellow warning, continuing offline")
    segments.set_all(YELLOW)
    segments.show()
    sleep_ms(2000)
    segments.clear()
    return False

# -------------------- Main Loop --------------------
def main():
    global _wdt
    cfg = load_config()

    # Brightness: saved value (from buttons) wins over config default
    step = cfg["brightness_step"]
    min_b = cfg["min_brightness"]
    saved = load_saved_brightness()
    brightness = clamp(saved if saved is not None else cfg["brightness"], min_b, 1.0)

    segments = Segments(cfg["pins"], cfg["layout_led_counts"], cfg["gamma"])
    segments.brightness = brightness
    segments.clear()

    online = startup(segments, cfg)
    synced = sync_time(cfg) if online else False
    last_sync_attempt = time.ticks_ms()

    values = cfg["segment_order"]
    table = build_patterns(values)

    btn_down = Button(cfg["button_down_pin"])
    btn_up = Button(cfg["button_up_pin"])

    if cfg["enable_watchdog"]:
        _wdt = machine.WDT(timeout=8000)
        print("Watchdog enabled")

    last_shown = None
    save_due = None
    last_warn = time.ticks_ms()
    resync_ms = int(cfg["ntp_resync_hours"] * 3600 * 1000)
    retry_ms = 5 * 60 * 1000   # retry every 5 min while never synced

    while True:
        feed()
        now = time.ticks_ms()
        redraw = False

        # --- Buttons (checked every ~20 ms, so no missed presses) ---
        new_b = brightness
        if btn_down.fired(now):
            new_b -= step
        if btn_up.fired(now):
            new_b += step
        if new_b != brightness:
            brightness = clamp(round(new_b / step) * step, min_b, 1.0)
            print("Brightness: {:.2f}".format(brightness))
            save_due = time.ticks_add(now, 5000)   # save once you stop pressing
        if save_due is not None and time.ticks_diff(now, save_due) >= 0:
            save_brightness(brightness)
            save_due = None

        # --- Periodic NTP re-sync ---
        interval = resync_ms if synced else retry_ms
        if cfg["wifi_ssid"] and time.ticks_diff(now, last_sync_attempt) > interval:
            last_sync_attempt = now
            if wifi_start(cfg) and (wifi_connected() or wifi_wait(10)):
                if sync_time(cfg):
                    synced = True
                    last_shown = None

        # --- Time ---
        t = get_local_time(cfg["timezone_offset_hours"])
        hour, minute = t[3], t[4]
        h12 = hour % 12 or 12
        m5 = minute // 5

        # Only change the pattern when the displayed value changes,
        # otherwise random patterns would jump around every minute.
        if (h12, m5) != last_shown:
            last_shown = (h12, m5)
            colors = compute_colors(table, segments.n, h12, m5, cfg["random_patterns"])
            for i, c in enumerate(colors):
                segments.set(i, c)
            redraw = True

        eff = effective_brightness(brightness, hour, cfg)
        if eff != segments.brightness:
            segments.brightness = eff
            redraw = True

        if redraw:
            segments.show()

        # --- Not synced: short yellow flash every 30 s ---
        if not synced and time.ticks_diff(now, last_warn) > 30000:
            last_warn = now
            segments.flash(YELLOW, 300)

        time.sleep_ms(20)

if __name__ == "__main__":
    main()
