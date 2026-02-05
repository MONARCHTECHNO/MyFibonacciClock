# Fibonacci Clock for Raspberry Pi Pico W (MicroPython)
# Inspired by: https://nerdcave.xyz/docs/projects/fibonnaci-clock/
# Improvements by Marcial:
#   - Startup Wi-Fi connection animation (color sweep) with timeout
#   - Real-time brightness control via GPIO6 (down) / GPIO7 (up)
#   - Better error handling and code organization
#   - Enhanced config loading with defaults, type checks, and merging
#   - Optional startup animation config (enable/disable, custom colors)
#   - NTP sync retry logic

import machine
import time
import ujson
import neopixel

try:
    import network
    import ntptime
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

# -------------------- Utilities --------------------
def load_config():
    default_config = {
        "wifi_ssid": "",
        "wifi_password": "",
        "timezone_offset_hours": 8,
        "brightness": 0.8,
        "layout_led_counts": [32, 12, 5, 2, 2],
        "segment_order": [5, 3, 2, 1, 1],
        "pins": [1, 2, 3, 4, 5],
        "single_data_pin_mode": False,
        "single_data_pin": 2,
        "total_leds_singlepin": 53,  # Adjusted example total
        "ntp_host": "ntp.aliyun.com",
        "enable_startup_animation": True,
        "startup_colors": [(255, 0, 0), (0, 255, 0), (0, 0, 255)],
        "startup_timeout_seconds": 60  # New: max wait time for WiFi
    }

    try:
        with open("config.json", "r") as f:
            user_config = ujson.loads(f.read())
            config = default_config.copy()
            config.update(user_config)

            # Type conversions and clamps
            config["brightness"] = float(clamp(config.get("brightness", 0.8), 0.0, 1.0))
            config["timezone_offset_hours"] = int(config.get("timezone_offset_hours", 8))
            config["single_data_pin_mode"] = bool(config.get("single_data_pin_mode", False))
            config["enable_startup_animation"] = bool(config.get("enable_startup_animation", True))
            config["startup_timeout_seconds"] = int(config.get("startup_timeout_seconds", 60))

            print("Config loaded successfully from config.json")
            return config

    except (OSError, ValueError) as e:
        print(f"Config load failed ({e}), using defaults")
        return default_config
    except Exception as e:
        print(f"Unexpected config error: {e}, using defaults")
        return default_config

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def scale_color(c, brightness):
    return tuple(int(clamp(x * brightness, 0, 255)) for x in c)

# Colors
RED    = (255, 0,   0)
GREEN  = (0,   255, 0)
BLUE   = (0,   0,   255)
BLACK  = (0,   0,   0)
YELLOW = (255, 255, 0)  # New: for WiFi timeout error indication

# -------------------- Fibonacci logic --------------------
def subset_sum_indices(values, target):
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i], reverse=True)
    def backtrack(i, t, chosen):
        if t == 0:
            return set(chosen)
        if i >= n or t < 0:
            return None
        idx = order[i]
        res = backtrack(i+1, t - values[idx], chosen + [idx])
        if res is not None:
            return res
        return backtrack(i+1, t, chosen)
    return backtrack(0, target, [])

def compute_state(values, hour, minute):
    h = hour % 12
    if h == 0: h = 12
    m5 = minute // 5
    hset = subset_sum_indices(values, h) if h > 0 else set()
    mset = subset_sum_indices(values, m5) if m5 > 0 else set()
    state = [0] * len(values)
    for i in range(len(values)):
        if i in hset and i in mset:
            state[i] = 3   # both (green)
        elif i in hset:
            state[i] = 1   # hour (red)
        elif i in mset:
            state[i] = 2   # minute (blue)
        else:
            state[i] = 0
    return state

# -------------------- Hardware --------------------
class SegmentsMultiPin:
    def __init__(self, pins, led_counts, brightness):
        self.n = len(pins)
        self.np = []
        self.counts = led_counts
        self._brightness = brightness
        for p, cnt in zip(pins, led_counts):
            pin = machine.Pin(p, machine.Pin.OUT)
            self.np.append(neopixel.NeoPixel(pin, cnt))

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        self._brightness = value

    def fill_segment(self, idx, color):
        col = scale_color(color, self.brightness)
        strip = self.np[idx]
        for i in range(self.counts[idx]):
            strip[i] = col
        strip.write()

    def clear_all(self):
        for idx in range(self.n):
            self.fill_segment(idx, BLACK)

class SegmentsSinglePin:
    def __init__(self, data_pin, led_counts, brightness):
        self.counts = led_counts
        self.offsets = []
        offset = 0
        for cnt in led_counts:
            self.offsets.append(offset)
            offset += cnt
        self.total = offset
        self._brightness = brightness
        pin = machine.Pin(data_pin, machine.Pin.OUT)
        self.np = neopixel.NeoPixel(pin, self.total)

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        self._brightness = value

    def fill_segment(self, idx, color):
        col = scale_color(color, self.brightness)
        start = self.offsets[idx]
        cnt = self.counts[idx]
        for i in range(start, start + cnt):
            self.np[i] = col
        self.np.write()

    def clear_all(self):
        for i in range(self.total):
            self.np[i] = (0, 0, 0)
        self.np.write()

# -------------------- WiFi and Time --------------------
def connect_wifi(ssid, pwd, timeout=15):
    if not WIFI_AVAILABLE or not ssid:
        return False
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return True
    wlan.connect(ssid, pwd)
    t0 = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), t0) > timeout * 1000:
            print("WiFi connection timeout")
            return False
        time.sleep(0.2)
    print("WiFi connected:", wlan.ifconfig()[0])
    return True

def sync_time(cfg, retries=3):
    if not WIFI_AVAILABLE:
        return False
    ntptime.host = cfg.get("ntp_host", "ntp.aliyun.com")
    for attempt in range(retries):
        try:
            ntptime.settime()
            print("Time synced on attempt", attempt + 1)
            return True
        except Exception as e:
            print(f"NTP sync attempt {attempt + 1} failed:", e)
            time.sleep(2)
    print("NTP sync failed after retries")
    return False

def get_local_time(tz_hours=8):
    return time.gmtime(time.time() + int(tz_hours * 3600))

# -------------------- Startup Animation --------------------
def startup_animation(segments, cfg):
    if not cfg["enable_startup_animation"]:
        print("Startup animation disabled")
        connect_wifi(cfg["wifi_ssid"], cfg["wifi_password"], 10)  # Quick connect without animation
        return

    COLORS = cfg["startup_colors"]
    print("Starting WiFi connection animation...")
    t0 = time.ticks_ms()
    max_time = cfg["startup_timeout_seconds"] * 1000
    wlan = network.WLAN(network.STA_IF) if WIFI_AVAILABLE else None
    if WIFI_AVAILABLE and cfg["wifi_ssid"]:
        wlan.active(True)
        wlan.connect(cfg["wifi_ssid"], cfg["wifi_password"])

    while True:
        if WIFI_AVAILABLE and wlan.isconnected():
            print("WiFi connected → starting clock")
            segments.clear_all()
            break
        if time.ticks_diff(time.ticks_ms(), t0) > max_time:
            print("WiFi timeout → showing error (yellow) and proceeding offline")
            for idx in range(len(segments.counts)):
                segments.fill_segment(idx, YELLOW)
            time.sleep(2)
            segments.clear_all()
            break
        for color in COLORS:
            for idx in range(len(segments.counts)):
                segments.fill_segment(idx, color)
                time.sleep(0.15)
            time.sleep(0.3)

# -------------------- Main Loop --------------------
def main():
    cfg = load_config()
    values = cfg["segment_order"]
    led_counts = cfg["layout_led_counts"]
    brightness = cfg["brightness"]
    tz = cfg["timezone_offset_hours"]

    # Initialize LEDs
    if cfg["single_data_pin_mode"]:
        segments = SegmentsSinglePin(cfg["single_data_pin"], led_counts, brightness)
    else:
        segments = SegmentsMultiPin(cfg["pins"], led_counts, brightness)

    segments.clear_all()

    # Startup animation (handles WiFi connect)
    startup_animation(segments, cfg)

    # Time sync with retries
    sync_time(cfg)

    # Brightness buttons
    btn_down = machine.Pin(6, machine.Pin.IN, machine.Pin.PULL_UP)
    btn_up   = machine.Pin(7, machine.Pin.IN, machine.Pin.PULL_UP)
    last_down = 1
    last_up   = 1
    last_min  = -1

    while True:
        # Brightness adjustment
        if btn_down.value() == 0 and last_down == 1:
            brightness = clamp(brightness - 0.1, 0.0, 1.0)
            segments.brightness = brightness
            print(f"Brightness: {brightness:.1f}")
            last_min = -1  # Force refresh
            time.sleep(0.25)
        last_down = btn_down.value()

        if btn_up.value() == 0 and last_up == 1:
            brightness = clamp(brightness + 0.1, 0.0, 1.0)
            segments.brightness = brightness
            print(f"Brightness: {brightness:.1f}")
            last_min = -1
            time.sleep(0.25)
        last_up = btn_up.value()

        # Time update
        y, mo, d, h, m, s, wd, yd = get_local_time(tz)
        if m != last_min:
            last_min = m
            state = compute_state(values, h, m)
            for i, s in enumerate(state):
                color = BLACK if s == 0 else RED if s == 1 else BLUE if s == 2 else GREEN
                segments.fill_segment(i, color)
        time.sleep(1)

if __name__ == "__main__":
    main()