/*
 VBT Trainer Project - Samuel Smith - Spring 2026
sibsmith@bu.edu | sibsmith.ithaca@gmail.com
*/
#include <Arduino.h> // Core: pinMode, digitalRead, millis, Serial
#include <ESP32Encoder.h> // Harware pulse counter -- performs better than interrupts
#include <Adafruit_GFX.h>      // Graphics base library for OLED
#include <Adafruit_SSD1306.h>  // OLED driver
#include <Wire.h> //I2C protocol -- needed for OLED
#include <NimBLEDevice.h> // Bluetooth Low Energy
#include "config.h" //imports custom pin definitions and constants

ESP32Encoder encoder;

// Velocity Tracking
float velocityBuffer[SMOOTHING_WINDOW]; //Circular buffer for moving average
int bufferIndex = 0; //Index for tracking buffer position
float smoothVelocity = 0.0; //Value of the smoothed velocity
float peakVelocity = 0.0; //Highest velocity in the calculated rep window
long lastPulseCount = 0; //Encoder count at last velocity sample
unsigned long lastSampleTime = 0; //Timestamp of last velocity sample (ms)

// Rep detection
bool repInProgress = false; // Checks to see if we are currently in a rep
int repCount = 0; // Total reps in the session
float repStartVelocity = 0.0; // Velocity at the start of the rep 
float meanConcentricVelo = 0.0; //Mean Concentric Velocity for the completed repetition
// **Mean Concentric Velocity (MCV)** Average velocity of the barbell during the rep
float velocitySumThisRep = 0.0; // Sum of the velocity samples during concentric phase
int samplesThisRep = 0; // Number of sampels taken during the concentric phase of the rep
unsigned long repStartTime = 0; // When this rep started (ms)

// Session Tracking
float setPeakVelocity = 0.0; // MCV of the rep with the highest velocity (to calculate velocity loss %)
float velocityLoss = 0.0; // Signed percent change from peak rep to most recent rep
// OLED 
Adafruit_SSD1306 display(128, 64, &Wire, -1);

// Bluetooth LE 
NimBLEServer* bleServer = nullptr;
NimBLECharacteristic* bleCharVelocity = nullptr;
bool bleClientConnected = false;
unsigned long lastBLEUpdate = 0; // timestamp of last BLE broadcast
class ServerCallbacks : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* server) override {

        bleClientConnected = true;

        Serial.println("BLE: phone connected");

    }
        void onDisconnect(NimBLEServer* server) override {

        bleClientConnected = false;

        Serial.println("BLE: phone disconnected — advertising again");

        server->startAdvertising();  // Auto-restart advertising so phone can reconnect

    }
};

void setupBLE(){
    NimBLEDevice::init(BLE_DEVICE_NAME);  // Initialize with your device name
    bleServer = NimBLEDevice::createServer();
    bleServer->setCallbacks(new ServerCallbacks());
    //Create the service - service being the catagory of data, in this case vbt velocity data
    NimBLEService* service = bleServer->createService(SERVICE_UUID);
    bleCharVelocity = service->createCharacteristic(CHARACTERISTIC_UUID, NIMBLE_PROPERTY::NOTIFY);
    service->start(); 
    // begins advertizing existence so phone can connect 
    NimBLEAdvertising* advertising = NimBLEDevice::getAdvertising();
    advertising->addServiceUUID(SERVICE_UUID);
    advertising->start();
    Serial.println("BLE: advertising as '" BLE_DEVICE_NAME "'");
}
// HELPER FUNCTIONS ---------------------
// calculateVelocity: Returns raw velocity in m/s when called every 200Hz/5ms in loop()
float calculateVelocity() {
    unsigned long now = millis(); // Gets current time in ms
    long nowCount = encoder.getCount(); // Gets the current encoder pulse count
    unsigned long dt_ms = now - lastSampleTime; // Time delta between last sample (ms)
    long dp = (nowCount - lastPulseCount) * CONCENTRIC_SIGN; // Pulses since last sample
    // Update "last" values for next function call
    lastSampleTime = now;
    lastPulseCount = nowCount;
    //Safeguard: if not time has passed, avoide devide-by-zero error
    if (dt_ms == 0) return 0.0;
    //Convert pulses to mm and milliseconds to seconds to get velocity
    //Calculation is (meters/second) = pulses * mm/pulse * 1 meter / 1000 mm * 1000 ms/1s * 1/dt_ms
    float displacement_mm = dp * MM_PER_PULSE; //total mm moved
    float velocity_ms = (displacement_mm/1000.0)/(dt_ms/1000.0); //mm -> meters, ms -> seconds (meters/second)
    //Given we only want the upward velocity, the velocity must have a sign to denote direction
    return velocity_ms;
}

// logToSerial: logs the timestamp (ms), rawVelocity value, and smoothVel value in csv format
void logToSerial(unsigned long timestamp, float rawVelocity, float smoothVel, int rep) {
    // Format: timestamp_ms, raw_velocity, smooth_velocity, rep_number
    Serial.print(timestamp);
    Serial.print(",");
    Serial.print(rawVelocity, 4);   // 4 decimal places
    Serial.print(",");
    Serial.print(smoothVel, 4);
    Serial.print(",");
    Serial.println(rep);            // println adds newline — Python reads line by line
}

//updateDisplay: called after each rep is completed and at every 100ms interval during the rep
void updateDisplay(float mcv, int reps, float velocity, float vLoss) {
    display.clearDisplay(); //Clear display of any existing text
    display.setTextColor(SSD1306_WHITE);
    //LINE 1: Large text displaying LIVE VELOCITY
    display.setTextSize(2); 
    display.setCursor(0, 0);
    display.print(mcv, 2);   // Round velocity to 2 decimal places
    display.print(" m/s");
    //LINE 2: Displays a rep counter for current exercise
    display.setTextSize(1);
    display.setCursor(0, 22);
    display.print("Reps: "); //Prints "reps" before the number that gets updated
    display.print(reps);
    //LINE 3: Last rep MCV
    display.setCursor(0, 32);
    display.print("Peak: ");
    display.print(velocity, 2); //Rounds mcv to 2 decimal places, consistent with velo
    display.print(" m/s");
    // Line 4: Velocity loss %
    display.setCursor(0, 42);
    display.print("VL%: ");
    display.print(vLoss, 1);
    display.print("%");
    // Line 5: BLE status
    display.setCursor(0, 54);
    display.print(bleClientConnected ? "BLE: connected" : "BLE: waiting...");
    display.display(); //Push buffer to screen — nothing shows until this is called
}

//sendBleUpdate: When called, packages current rep data as JSON string 
//formatted as {"v":1.23,"reps":3,"mcv":1.18,"vl":4.2} and sends as BLE packet
void sendBleUpdate(float velocity, int reps, float mcv, float vLoss) {
    if (!bleClientConnected) return;  // Immedate return if not bluetooth connection is established
    // Sample JSON string is as follows: {"v":1.23,"reps":3,"mcv":1.18,"vl":4.2}
    char jsonBuffer[80]; // If number of reps gets too high, this may crash the buffer of only 80
    snprintf(jsonBuffer, sizeof(jsonBuffer),
        "{\"v\":%.2f,\"reps\":%d,\"mcv\":%.2f,\"vl\":%.1f}", velocity, reps, mcv, vLoss);
    bleCharVelocity->setValue((uint8_t*)jsonBuffer, strlen(jsonBuffer));
    bleCharVelocity->notify();  //Push to any subscribed phone
}

// smoothVelocityReading: takes the float of the newest velocity sample "newSample" 
// and returns a new smoothed average given the defined SMOOTHING_WINDOW
float smoothVelocityReading(float newSample){
    velocityBuffer[bufferIndex] = newSample; // Stores new sample
    bufferIndex = (bufferIndex + 1) % SMOOTHING_WINDOW; // Advances buffer index 
    // % (modulus) wraps back to 0
    // Calculate the average of all samples in buffer
    float sum = 0.0;
    for (int i = 0; i<SMOOTHING_WINDOW; i++){
        sum += velocityBuffer[i];
    }
    return sum/SMOOTHING_WINDOW;
}


void setup(){
    //_________________________ SERIAL _________________________
    Serial.begin(115200);
    Serial.println("VBT Trainer starting...");
    //_________________________ BUTTON _________________________
    pinMode(RESET_BUTTON_PIN, INPUT_PULLUP);

    // ENCODER
    ESP32Encoder::useInternalWeakPullResistors = puType::up; //enable internat pull-up resistors
    encoder.attachFullQuad(ENCODER_PIN_A, ENCODER_PIN_B);
    encoder.setCount(0); // Zero the counter when starting up
    Serial.println("Encoder initialized on GPIO " + String(ENCODER_PIN_A) + "and" + String(ENCODER_PIN_B));
    //Initialized velocity buffer to be zero
    for (int i=0; i<SMOOTHING_WINDOW; i++){
        velocityBuffer[i] = 0.0;
    }
    
    //_________________________ OLED _________________________
    Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);  // Start I2C on the pins from config.h
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
        // If OLED doesn't initialize, print error and continue without it
        Serial.println("WARNING: OLED not found — check wiring"); 
        // Prints a display isn't functioning message   
    } else {
        // initialization messages
        display.clearDisplay();
        display.setTextSize(1);
        display.setTextColor(SSD1306_WHITE);
        display.setCursor(0, 0);
        display.println("VBT Trainer");
        display.println("Ready... ");
        display.clearDisplay();
        display.println("Setup complete. Waiting for lifts...");
        Serial.println("OLED initialized"); // Prints initialization to Serial
    }
    //_________________________ BLE _________________________
    setupBLE();
    //_________________________ Record Start Time _________________________
    lastSampleTime = millis(); //Grabs the current time
    Serial.println("Setup complete. Waiting for lifts..."); 

}
/*
void loop(){
    int stateA = digitalRead(18);
    int stateB = digitalRead(19);
    Serial.print("A: ");
    Serial.print(stateA);
    Serial.print("B ");
    Serial.print(stateB);
    delay(100);
} 
*/
void loop() {
    int buttonState = digitalRead(RESET_BUTTON_PIN); // Immediately reads 
    if (buttonState == 0) {
        repCount = 0;
        repInProgress = false;
        meanConcentricVelo = 0.0;
        peakVelocity = 0.0;
        velocityLoss = 0.0;
        setPeakVelocity = 0.0;
        updateDisplay(0.00, 0, 0.00, 0);
    }
    unsigned long now = millis(); // Get current time once per loop iteration
    //TASK 1: Calculate velocity at 200Hz
    if (now - lastSampleTime >= (1000/SAMPLE_RATE_HZ)){
        float rawVel = calculateVelocity();
        smoothVelocity = smoothVelocityReading(rawVel);
        logToSerial(now, rawVel, smoothVelocity, repCount);    
        //Task 1a: Rep detection
        //Check to see if a rep is already in progress
        if (!repInProgress) {
            //If rep is not in progress, one is started
            
            if (smoothVelocity > REP_START_VELOCITY) {
                repInProgress = true; //change bool for reps
                repStartTime = now; //set the rep start time to now
                peakVelocity = smoothVelocity; //set the peak velocity to the velocity at the start
                velocitySumThisRep = smoothVelocity; //Begin to sum velocities with first sample
                samplesThisRep = 1; 
            }
        }
        // Else means rep is in progress - data collection is active
        else {
            velocitySumThisRep += smoothVelocity;
            samplesThisRep ++;
            if (smoothVelocity > peakVelocity) {
                peakVelocity = smoothVelocity;
            }

            //Check to see if the rep has ended based on thresholds set in config.h
            //The two criteria for this are: 
            //1. The velocity drops below threshold. 
            //2. The duraction minimum is met to prevent false positive reps
            bool velocityDropped = smoothVelocity < REP_END_VELOCITY; 
            bool longEnough = (now - repStartTime) > REP_MIN_DURATION_MS;
            if (velocityDropped && longEnough){
                //Below is calculated when the rep is complete
                repInProgress = false; //program knows rep is over
                repCount ++; //count the final rep
                meanConcentricVelo = velocitySumThisRep / samplesThisRep; // calculate MCV
                // Store first rep velocity for VL% calculation
                /* Logic of VL% - Velocity Loss % = (peakRep - repN) / peakRep * 100
                -If on rep1 --> assign peak to rep1
                -If on rep2 or later, there are three cases:
                    1. repN < rep1 --> imediately calculate velocity change
                    2. repN+1 > repPeak --> calculate velocity change AND set peak to repN+1 MCV
                    3. repN+1 = repN --> velocity change is 0, but need to check for this case
                */

                if (repCount == 1) {
                    setPeakVelocity = meanConcentricVelo;
                }
                if (setPeakVelocity > 0){
                    velocityLoss = ((setPeakVelocity - meanConcentricVelo)/ setPeakVelocity) * 100.0 * -1; // Case 1 (and 3)

                    if (meanConcentricVelo > setPeakVelocity){
                        // After loss (or gain in this case) is calculated, set the new repPeak
                        setPeakVelocity = meanConcentricVelo;
                    }
                }
                
                // Log completed rep summary (starts with # so Python can parse separately)
                Serial.print("# REP,");
                Serial.print(repCount);
                Serial.print(",");
                Serial.print(meanConcentricVelo, 3);
                Serial.print(",");
                Serial.print(peakVelocity, 3);
                Serial.print(",");
                Serial.println(velocityLoss, 1);
                // Update display immediately after rep
                updateDisplay(meanConcentricVelo, repCount, peakVelocity, velocityLoss);

            }
        }
    }
    // Task 2: Send BLE update at 10Hz
    if (now - lastBLEUpdate >= (1000 / BLE_BROADCAST_HZ)) {
        lastBLEUpdate = now;
        sendBleUpdate(smoothVelocity, repCount, meanConcentricVelo, velocityLoss);
    }
    
}
