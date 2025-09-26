const int pins[] = {2, 4, 7, 8};   // Output pins
int ledSensePin = A0;               // Analog pin for LED sensing
float voltageThreshold = 1.5;       // Threshold for LED ON

bool alertDetected = false;         // Track alert state
unsigned long lastCheck = 0;
const unsigned long checkInterval = 1000; // Check every 1 second

void setup() {
  Serial.begin(9600);

  // Initialize output pins
  for (int i = 0; i < 4; i++) {
    pinMode(pins[i], OUTPUT);
    digitalWrite(pins[i], HIGH); // Start ON
  }

  Serial.println("Ready for commands like t1lp, t2dp, t3ho, t4lo, etc.");
  Serial.println("Monitoring tag LED for alerts...");
}

void loop() {
  unsigned long currentMillis = millis();

  // --- Button press commands ---
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() >= 4 && input.charAt(0) == 't') {
      int pinIndex = input.charAt(1) - '1';
      String action = input.substring(2);

      if (pinIndex >= 0 && pinIndex < 4) {
        int pin = pins[pinIndex];

        if (action == "lp") {
          digitalWrite(pin, LOW);
          delay(3000);
          digitalWrite(pin, HIGH);
          Serial.print("Pin "); Serial.print(pin); Serial.println(": Long press done");

        } else if (action == "sp") {
          digitalWrite(pin, LOW);
          delay(300);
          digitalWrite(pin, HIGH);
          Serial.print("Pin "); Serial.print(pin); Serial.println(": Short press done");

        } else if (action == "dp") {
          for (int i = 0; i < 2; i++) {
            digitalWrite(pin, LOW);
            delay(300);
            digitalWrite(pin, HIGH);
            delay(300);
          }
          Serial.print("Pin "); Serial.print(pin); Serial.println(": Double press done");

        } else if (action == "ho") {
          digitalWrite(pin, LOW);
          Serial.print("Pin "); Serial.print(pin); Serial.println(": Set LOW (OFF)");

        } else if (action == "lo") {
          digitalWrite(pin, HIGH);
          Serial.print("Pin "); Serial.print(pin); Serial.println(": Set HIGH (ON)");

        } else {
          Serial.println("Unknown action");
        }

      } else {
        Serial.println("Invalid pin index");
      }
    } else {
      Serial.println("Invalid command format");
    }
  }

  // --- LED alert detection (1 second window) ---
  // --- LED alert detection (1 second window) ---
if (currentMillis - lastCheck >= checkInterval) {
    lastCheck = currentMillis;

    bool ledOnDetected = false;
    unsigned long startMillis = millis();

    // --- New variables for blink counting and duration ---
    bool lastLedState = false;       // Track previous LED state
    int blinkCount = 0;              // Number of LED blinks
    unsigned long ledOnTime = 0;     // Total LED ON duration
    unsigned long ledOnStart = 0;    // Time when LED turned ON

    // Sample LED for 1 second to detect blinking
    while (millis() - startMillis < 1000) {
        int sensorValue = analogRead(ledSensePin);
        float voltage = sensorValue * (5.0 / 1023.0);
        bool ledState = (voltage > voltageThreshold);

        // Detect rising edge → increment blink count
        if (ledState && !lastLedState) {
            blinkCount++;
            ledOnStart = millis(); // Start of LED ON period
        }

        // Detect falling edge → accumulate ON duration
        if (!ledState && lastLedState) {
            ledOnTime += millis() - ledOnStart;
        }

        lastLedState = ledState;

        // Keep track of LED ON at least once
        if (ledState) {
            ledOnDetected = true;
        }
    }

    // If LED is still ON at end of sampling, add remaining time
    if (lastLedState) {
        ledOnTime += millis() - ledOnStart;
    }

    // Report alert only on state change
    if (ledOnDetected && !alertDetected) {
        Serial.print("ALERT: LED blinking detected");
        Serial.print("  Blinks: "); Serial.print(blinkCount);
        Serial.print("  Total ON duration (ms): "); Serial.println(ledOnTime);
        alertDetected = true;
    } else if (!ledOnDetected && alertDetected) {
        Serial.println("Alert cleared");
        alertDetected = false;
    }
}

}
