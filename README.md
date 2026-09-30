# VBT Trainer

A DIY velocity-based training (VBT) device that measures barbell speed in real time. A spring-loaded spool with a 600 PPR rotary encoder measures bar displacement, and an ESP32 turns that into velocity, rep metrics, an on-device display, BLE output, and CSV logs.

<!-- TODO: add a photo of the working prototype here -->

## What it does

- Measures barbell velocity from tether displacement (spool + 600 PPR quadrature encoder, about 0.049 mm resolution per count)
- Computes velocity at 200 Hz with a 5-sample moving average and automatic rep detection
- Per-rep metrics: mean concentric velocity (MCV), peak velocity, velocity loss %; with load entered: estimated 1RM, average and peak power
- Shows live output on a 0.96" SSD1306 OLED, with a physical reset button
- Broadcasts data over BLE at 10 Hz
- Logs every session to CSV over serial for analysis in Python

**Status:** working prototype. Accuracy has not yet been validated against a commercial reference device (see [Validation](#validation)).

## System architecture

```
 bar --tether--> spool --> encoder (A/B) --> ESP32 --> OLED (I2C)
                                               |--> BLE
                                               '--> USB serial --> python/serial_logger.py --> CSV --> analysis
```

<!-- TODO: replace with a proper diagram (docs/architecture.png) -->

## Bill of materials

| Part | Model | Approx. cost |
|------|-------|--------------|
| Microcontroller | ESP32 DevKit v1 (PlatformIO board `esp32dev`) | $9 |
| Encoder | 600 PPR quadrature rotary encoder | $18 |
| Display | SSD1306 0.96" I2C OLED | $3 |
| Battery | Samsung 30Q 18650 (INR18650-30Q, 3000 mAh) | $4 |
| Battery holder | 18650 holder | $10 |
| Resistors | 2x 10 kOhm (encoder pull-ups) | <$1 |
| Push button | Momentary, for reset | <$1 |
| Tether mechanism | Spring-loaded spool, 37.47 mm effective diameter | varies |

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
python python/serial_logger.py   # <!-- TODO: document serial port / baud arguments -->
```

Each session writes two files to `data/sessions/`, named `YYYY-MM-DD_HH-MM_raw.csv` (per-sample) and `..._reps.csv` (per-rep summary). Raw columns include `timestamp_ms`, `raw_velocity`, `smooth_velocity` (m/s) and `rep_num` (0 = no rep in progress). <!-- TODO: list the full raw and reps column sets -->

`data/sample_session.csv` is a small example to try the analysis scripts on.

### 4. Analyze and calibrate

```bash
# Plot a session
python python/analysis/calibration.py plot data/sessions/2026-05-31_19-05_raw.csv

# Fit the scale factor from free-fall drops (heights in m, measured peak velocity in m/s)
python python/analysis/calibration.py fit --heights 0.25 0.50 0.75 1.00 --velocities V1 V2 V3 V4
```

Calibration compares peak velocity at the end of a free-fall drop against `v = sqrt(2gh)` and fits a least-squares scale factor `k`. My results: [`docs/calibration_results.md`](docs/calibration_results.md).

Other scripts: `python/live_plot.py` (live plotting), `python/analysis/session_analysis.py`, `python/analysis/load_velocity.py`. <!-- TODO: one line each on usage -->

### BLE
Device name `VBT-Trainer-V_0`. Service UUID `209ec59d-a3ea-40c6-ae45-e495047cff05`, characteristic UUID `85f3ab78-fdfb-4c16-8b9e-1a324e287fb3`. <!-- TODO: document the packet format -->

## Validation

To compare against a reference device such as a GymAware:

1. Mount both devices on the same barbell and record the same sets simultaneously
2. Use a range of loads and speeds (slow grinders through fast, light reps)
3. Match reps one-to-one and compare MCV and peak velocity per rep. Note that rep-detection thresholds in `config.h` affect which reps are counted, so check rep counts agree first.
4. Report mean bias, limits of agreement (Bland-Altman), and correlation

Results will go in `docs/validation.md`. <!-- TODO -->

## Repository structure

```
firmware/   ESP32 firmware (PlatformIO / Arduino, C++)
python/     Serial logger, live plot, and analysis/calibration scripts
hardware/   BOM, KiCad PCB project, CAD and drawings
data/       Example and logged session CSVs
docs/       Wiring, calibration results, design decisions
```

## Roadmap

- [x] Sensor validation
- [x] Firmware + Python pipeline (working prototype)
- [ ] Housing design and fabrication
- [ ] Validation against a reference VBT
- [ ] Custom PCB carrier board (KiCad project in `hardware/pcb/`)
- [ ] Phone app / dashboard

## License

MIT - see [LICENSE](LICENSE).
