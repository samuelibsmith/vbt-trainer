# VBT Trainer

A DIY velocity-based training (VBT) device that measures barbell speed in real time. A spring-loaded spool with a 600 PPR rotary encoder measures bar displacement, and an ESP32 turns that into velocity, rep metrics, an on-device display, BLE output, and CSV logs.

<img width="898" height="1245" alt="IMG_3297" scsrc="https://github.com/user-attachments/assets/750e525b-e7e1-4ac2-8be5-ff30c8677d8b" />

## What it does

- Measures barbell velocity (±2% accuracy target) using a spring-loaded

  spool and 600 PPR rotary encoder

- Streams live velocity data over BLE to a phone app

- Logs session data to CSV for analysis

- Computes: MCV, peak velocity, velocity loss %, estimated 1RM, (using weight lifted: peak power, avg power)

## System Architecture

[diagram here — add later]

## Hardware

| Microcontroller | ESP32 DevKit v1 | $9 | 

| Encoder | Taiss 600PPR | $18 | 

| Display | SSD1306 0.96" OLED | $3 |

| Battery | Samsung 30Q 18650 3000mAh 15A Battery | $4 |

| Battery Holder | Samsung 30Q 18650 3000mAh 15A Battery | $10 |


Full list: [`hardware/bom.csv`](hardware/bom.csv)

## Wiring

| Signal | ESP32 pin | Notes |
|--------|-----------|-------|
| Encoder channel A | GPIO 18 | 10 kOhm pull-up to 3.3 V |
| Encoder channel B | GPIO 19 | 10 kOhm pull-up to 3.3 V |
| OLED SDA | GPIO 21 | I2C address 0x3C |
| OLED SCL | GPIO 22 | |
| Reset button | GPIO 4 | <!-- TODO: to GND with internal pull-up? confirm from main.cpp --> |
| Battery + | Vin | also powers the encoder directly |

Pins are defined in [`firmware/include/config.h`](firmware/include/config.h). Wiring notes: [`docs/wiring_diagram.md`](docs/wiring_diagram.md).

> **Power warning:** the current design connects a bare 18650 directly to Vin with no protection circuit or charger. Use a protected cell or a charger/protection module, and never leave the cell unattended while charging. Expect voltage sag (and possible brownouts) as the cell nears empty.

## Getting started

### 1. Build the hardware
Wire everything per the table above. Measure your own spool's effective diameter, because it sets the mm-per-count scale for every reading.

### 2. Flash the firmware
Requirements: VS Code with the PlatformIO extension (or the `pio` CLI).

1. Open the `firmware/` folder in PlatformIO. Libraries install automatically from `platformio.ini`.
2. Set `SPOOL_DIAMETER_MM` in `firmware/include/config.h` to your measured spool diameter (the repo default is 37.47).
3. Build and upload: `pio run -t upload`
4. Open the serial monitor at 115200 baud to confirm output: `pio device monitor`

Key settings in `config.h`:

| Setting | Default | Meaning |
|---------|---------|---------|
| `SAMPLE_RATE_HZ` | 200 | velocity calculation rate |
| `SMOOTHING_WINDOW` | 5 | moving-average length (samples) |
| `REP_START_VELOCITY` | 0.08 m/s | rep begins above this |
| `REP_END_VELOCITY` | 0.05 m/s | rep ends below this |
| `REP_MIN_DURATION_MS` | 150 | ignore shorter spikes |
| `BLE_BROADCAST_HZ` | 10 | BLE update rate |

### 3. Log data
Requires Python 3.9-3.12 (the pinned numpy 1.26 has no wheels for 3.13).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r python/requirements.txt

python python/serial_logger.py

## Build Log

- [X] Phase 1: Sensor validation

- [ ] Phase 2: Firmware + Python pipeline

- [ ] Phase 3: Housing design and fabrication

- [ ] Phase 4: Phone app + dashboard

## License

MIT - see [LICENSE](LICENSE).
