# Fibonacci Clock - Improved Version (Raspberry Pi Pico W)

A beautiful Fibonacci Clock project using **Raspberry Pi Pico W** and **MicroPython**.

**Inspired by**: [NerdCave.xyz Fibonacci Clock](https://nerdcave.xyz/docs/projects/fibonnaci-clock/)

**My Improvements**:
- Startup WiFi connection animation (color sweep across segments) with timeout
- Real-time brightness control using two buttons (GPIO6 ↓, GPIO7 ↑)
- Configurable via `config.json` (WiFi, timezone, brightness, LED counts, animation options, etc.)
- Better error handling, debug prints, and NTP sync retries
- Supports both multi-pin and single-pin LED strip modes

## Features
- Displays time in 12-hour format with Fibonacci squares (1,1,2,3,5)
- Red = hours, Blue = minutes, Green = overlap (both)
- WiFi + NTP time sync (Aliyun server for fast China access)
- Adjustable brightness (0.0–1.0)
- Optional startup animation (enable/disable, custom colors)

## Hardware
- Raspberry Pi Pico W
- WS2812B LED strips (example: 32+12+5+2+2 = 53 LEDs)
- Two push buttons (GPIO6 & GPIO7, pull-up)
- 5V power supply

## Software Requirements
- MicroPython firmware for Pico W
- Built-in libraries: `neopixel`, `network`, `ntptime`, `ujson`

## How to Use
1. Flash MicroPython to your Pico W
2. Edit `config.json` with your WiFi SSID/password (do NOT commit real credentials!)
3. Upload `main.py` and `config.json` to the Pico W (using Thonny, rshell, or ampy)
4. Power on → watch the startup animation while connecting to WiFi
5. Press GPIO6 to decrease brightness, GPIO7 to increase

## Photos / Demo


Huge thanks to the original author for the inspiration!

MIT License – feel free to use, modify, and share (with credit to originals).
