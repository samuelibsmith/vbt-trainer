#pragma once

#include <ESP32Encoder.h>  // The library you already use
#include "sensor.h"        // Our contract from file 1
#include "config.h"        // Your pin numbers and constants

// The ": public SpoolSensor" part means QuadSensor IS a SpoolSensor.
// It promises to fill in the three placeholder functions above,
// so it can be used anywhere a SpoolSensor is expected.
class QuadSensor : public SpoolSensor {

    // These three variables belong to each QuadSensor object.
    // Code outside the class cannot touch them (they sit above
    // any "public:" line, so they are private by default).
    ESP32Encoder enc;     // The pulse counter hardware object
    float mmPerPulse;     // This sensor's calibration value
    int sign;             // +1 or -1, your CONCENTRIC_SIGN

public:

    // The constructor: runs once when the object is created.
    // The part after the colon is an "initializer list": it fills
    // the member variables above with the values passed in, before
    // the (empty) body in {} runs.
    // Read it as: "my mmPerPulse gets the mmPerPulse I was given".
    QuadSensor(float mmPerPulse, int sign) : mmPerPulse(mmPerPulse), sign(sign) {}

    // "override" tells the compiler: this is my version of the
    // placeholder function from SpoolSensor, check I spelled it right.
    void begin() override {
        // These three lines are copied from your current setup(),
        // unchanged. They just live here now instead of in main.cpp.
        ESP32Encoder::useInternalWeakPullResistors = puType::up;
        enc.attachFullQuad(ENCODER_PIN_A, ENCODER_PIN_B);
        enc.setCount(0);
    }

    float displacementMM() override {
        // getCount() returns total pulses since power-on (a whole
        // number). Multiplying by mmPerPulse turns pulses into mm,
        // and by sign flips the direction if your encoder counts
        // "down" when the cord pays out. The result is a float
        // because mmPerPulse is a float.
        return enc.getCount() * mmPerPulse * sign;
    }

    const char* name() override { return "quad"; }
};
