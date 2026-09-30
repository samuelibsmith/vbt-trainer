# Power Circuit (v1 redesign: protected single-cell supply)

Status: **design, not yet built or tested.** Verify every IC pin number against the manufacturer datasheets before ordering a PCB.

## Goals
- Inserting the 18650 backwards causes no damage
- Cell is protected against over-discharge, over-current, and short circuit
- The ESP32 and encoder get a stable 5 V rail across the full cell range (about 3.0-4.2 V)

## Block diagram

```
Holder+ -> Q1 (reverse-polarity PMOS) -> F1 (PTC) -> SW1 -> U2 (5 V boost) -> +5V -> ESP32 VIN, encoder
Holder- -> B- -> [Q2 FS8205A, controlled by U1 DW01A] -> GND (P-)
                                                          ESP32 3V3 -> OLED, encoder pull-ups
```

The protection IC switches the **negative** leg, so the positive rail is simply the output of Q1.

## Nets

| Net | Description |
|-----|-------------|
| `CELL+` | Holder positive contact |
| `B-` | Holder negative contact (cell side of the protection MOSFETs) |
| `VBAT` | Protected battery positive, after Q1 |
| `GND` | System ground (P-, load side of the protection MOSFETs) |
| `VSW` | VBAT after F1 and SW1 |
| `+5V` | Boost converter output |
| `+3V3` | ESP32 onboard 3.3 V output (used by OLED and pull-ups) |

## Bill of materials

| Ref | Part | Value / model | Package | Notes |
|-----|------|---------------|---------|-------|
| BT1 | Single 18650 holder | - | - | Use a protected or unprotected cell; this circuit adds protection either way |
| Q1 | P-channel MOSFET | AO3401A (or similar, Vgs(th) under 1.5 V, Rds(on) under 100 mOhm) | SOT-23 | Reverse-polarity protection |
| U1 | Battery protection IC | DW01A | SOT-23-6 | Over-discharge, over-current, short circuit |
| Q2 | Dual N-MOSFET | FS8205A (8205A) | TSSOP-8 | Pairs with U1 |
| R1 | Resistor | 100 Ohm | 0603 | U1 supply filter |
| R2 | Resistor | 1 kOhm | 0603 | U1 current-sense input |
| C1 | Capacitor | 0.1 uF | 0603 | U1 supply decoupling |
| F1 | Resettable fuse (PTC) | about 1.5 A hold | 1812 or radial | Last-resort overcurrent limit |
| SW1 | Slide switch | SPDT, rated 1 A or more | - | Main power switch |
| U2 | 5 V boost converter | Module or IC, at least 0.5 A output at 3.0 V input (e.g. Pololu U1V11F5) | - | Check the datasheet for input-current limits |
| C2 | Capacitor | 10 uF | 0805 | Optional: extra bulk at U2 input |
| R3, R4 | Resistors | 10 kOhm | 0603 | Encoder A/B pull-ups to 3V3 |
| U3 | ESP32 DevKit v1 | - | - | 30-pin DevKit v1 |
| DS1 | OLED | SSD1306 0.96" I2C | - | 4-pin module |
| ENC1 | Rotary encoder | 600 P/R, 2-channel, NPN open-collector, 5-24 V | - | See wiring below |
| SW2 | Momentary button | - | - | Reset / rep button on GPIO 4 |

## Wiring

### Reverse-polarity protection

| From | To |
|------|----|
| BT1 + (`CELL+`) | Q1 **drain** (SOT-23 pin 3) |
| Q1 **source** (pin 2) | `VBAT` |
| Q1 **gate** (pin 1) | `GND` |

Correct insertion turns Q1 on. Reversed, Q1 stays off and blocks current.

### Cell protection (U1, Q2)

| From | To | Notes |
|------|----|-------|
| `VBAT` | R1 (100 Ohm), then U1 pin 5 (VCC) | |
| C1 | U1 VCC to U1 GND | Place close to U1 |
| U1 pin 6 (GND) | `B-` | |
| U1 pin 1 (OD) | Q2 pin 4 (G1) | Over-discharge gate |
| U1 pin 3 (OC) | Q2 pin 5 (G2) | Over-charge gate |
| U1 pin 2 (CS) | R2 (1 kOhm), then `GND` | Current sense |
| U1 pin 4 (TD) | not connected | Test pin |
| Q2 pins 2, 3 (S1) | `B-` | |
| Q2 pins 6, 7 (S2) | `GND` | |
| Q2 pins 1, 8 (D) | tie together, no other connection | Shared drain |
| BT1 - | `B-` | |

### Power path

| From | To |
|------|----|
| `VBAT` | F1 |
| F1 | SW1 common |
| SW1 output (`VSW`) | U2 VIN |
| U2 GND | `GND` |
| U2 VOUT (`+5V`) | ESP32 **VIN** pin |
| ESP32 GND | `GND` |

### Encoder (ENC1)

NPN open-collector outputs only pull a signal to ground, so each output needs a pull-up. **Pull up to 3.3 V, never 5 V**, because ESP32 GPIOs are not 5 V tolerant.

| Encoder wire (typical colors, verify on your unit) | To |
|----------------------------------------------------|----|
| Red (V+) | `+5V` |
| Black (0 V) | `GND` |
| Green (A) | ESP32 GPIO 18, and R3 (10 kOhm) to `+3V3` |
| White (B) | ESP32 GPIO 19, and R4 (10 kOhm) to `+3V3` |
| Shield (if present) | `GND` |

### Display (DS1) and button

| From | To |
|------|----|
| DS1 VCC | `+3V3` |
| DS1 GND | `GND` |
| DS1 SDA | ESP32 GPIO 21 |
| DS1 SCL | ESP32 GPIO 22 |
| SW2 one side | ESP32 GPIO 4 |
| SW2 other side | `GND` (assumed, confirm against `main.cpp`) |

## Bring-up checklist
1. Inspect all joints. Check continuity that `VBAT` and `GND` are not shorted, with no cell installed.
2. With SW1 **off**, insert the cell **backwards** deliberately. Measure `VBAT` and `+5V`: both should read about 0 V and nothing should get warm. Remove the cell.
3. Insert the cell correctly, SW1 still off. `VBAT` should read the cell voltage.
4. Turn SW1 on. `+5V` should read about 5 V and the ESP32 should boot.
5. Confirm encoder counts and display before doing anything else.

## Notes and limits
- **Charging is external.** Charge the cell in a separate 18650 charger. Adding an onboard TP4056-class charger is a future revision.
- **Keep SW1 off when connecting USB** so the USB supply and boost converter do not feed VIN together.
- **Protection cutoffs** for DW01A are around 2.4 V (over-discharge) with an over-current trip of several amps; check the datasheet for exact thresholds.
- This is a hobby design that has not been independently reviewed. Treat it as a starting point and do not leave a lithium cell unattended while testing.
