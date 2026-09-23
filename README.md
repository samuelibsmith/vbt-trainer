# VBT Trainer

A DIY velocity-based training (VBT) device that measures barbell speed 

in real time using a linear position transducer and ESP32 microcontroller.

Built as a portfolio project for mechanical engineering graduate study.

## What It Does

- Measures barbell velocity (±2% accuracy target) using a spring-loaded

  spool and 600 PPR rotary encoder

- Streams live velocity data over BLE to a phone app

- Logs session data to CSV for analysis

- Computes: MCV, peak velocity, velocity loss %, estimated 1RM, (using weight lifted: peak power, avg power)

## System Architecture

[diagram here — add later]

## V1 Hardware

| Microcontroller | ESP32 DevKit v1 | $9 | 

| Encoder | Taiss 600PPR | $18 | 

| Display | SSD1306 0.96" OLED | $3 |

| Battery | Samsung 30Q 18650 3000mAh 15A Battery | $4 |

| Battery Holder | Samsung 30Q 18650 3000mAh 15A Battery | $10 |


Full BOM: [hardware/bom.csv](hardware/bom.csv)

## Repository Structure

firmware/    # ESP32 firmware (PlatformIO/Arduino)

python/      # Data logging and analysis scripts

app/         # Phone app (Phase 4)

hardware/    # CAD files and engineering drawings

docs/        # Wiring diagrams, calibration results, design decisions

## Setup

### Firmware

1. Install VS Code + PlatformIO extension

2. Open firmware/ in PlatformIO

3. Update spool diameter in firmware/include/config.h

4. Upload to ESP32

### Python

pip install -r python/requirements.txt

python python/serial_logger.py

## Build Log

- [X] Phase 1: Sensor validation

- [ ] Phase 2: Firmware + Python pipeline

- [ ] Phase 3: Housing design and fabrication

- [ ] Phase 4: Phone app + dashboard

## License

MIT
