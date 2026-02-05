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

## Enclosure (STL) & PCB Files

### 3D-Printable Enclosure (STL)
All STL files are located in the [`stl/`](/stl/) folder.

I redesigned the enclosure in Fusion 360 based on the original concept, with the following improvements:
- Tighter tolerance for better part fit during assembly
- Added optional back cover for dust protection and cleaner appearance
- Optimized diffuser thickness and angle for more even light distribution
- Most parts designed to print without supports

**Recommended print settings**:
- Material: PLA or PETG
- Layer height: 0.2 mm
- Infill: 15–20%
- Supports: Usually not needed

### PCB (WS2812B Controller)
The PCB layout is **based on the original design** by Guitarman9119.

**Original PCB files**:  
https://github.com/Guitarman9119/Raspberry-Pi-Pico-/tree/main/WS2812B%20Controller

I used the original layout with only minor adjustments (if any):
- Slightly larger solder pads for easier hand-soldering
- Clearer silkscreen labels
- Optional repositioning of brightness control buttons (GPIO6 & GPIO7)

**Included in this repository** (`pcb/` folder):
- PCB preview/render images
- (Optional) My modified KiCad project files or Gerber export (if you made changes)

If you want the full original PCB design files (KiCad project), please refer directly to the link above.

Both STL and PCB files are provided for personal, non-commercial use and modification.

## How to Use
1. Flash MicroPython to your Pico W
2. Edit `config.json` with your WiFi SSID/password (do NOT commit real credentials!)
3. Upload `main.py` and `config.json` to the Pico W (using Thonny, rshell, or ampy)
4. Power on → watch the startup animation while connecting to WiFi
5. Press GPIO6 to decrease brightness, GPIO7 to increase

## How to Read the Fibonacci Clock 

At first glance, a Fibonacci Clock may look confusing, but it follows a simple set of rules.

### 1. Fibonacci Blocks 

The clock is made up of five blocks, each representing a Fibonacci number:
MONARCHTECHNO/MyFibonnaciClock/photos/IMG_3410.JPG

Each block may be lit in a different color depending on how it contributes to the time.

### 2. Color Meanings 

Each block uses color to indicate its purpose:

Red → Hours
Blue → Minutes
Green → Both hours and minutes
White → Not used
3. Reading the Hours 

To calculate the hour:

Add the values of all red blocks.
Add the values of all green blocks.
Hour = Red blocks + Green blocks

### 4. Reading the Minutes 

To calculate the minutes:

Add the values of all blue blocks.
Add the values of all green blocks.
Multiply the total by 5.
Minutes = (Blue blocks + Green blocks) × 5

### 5. Full Time Example 

**Demo**

MONARCHTECHNO/MyFibonnaciClock/photos/IMG_3446.JPG

Red block: 2
Blue block: 1
Green block: 5
Hour = Red blocks + Green blocks

Minutes = (Blue blocks + Green blocks) × 5

Then:

Hours = 2 + 5 = 7
Minutes = (1 + 5) × 5 = 30
➡️ The time is 7:30


Huge thanks to the original author for the inspiration!

MIT License – feel free to use, modify, and share (with credit to originals).
