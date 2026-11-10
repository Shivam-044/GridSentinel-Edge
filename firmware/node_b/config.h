#pragma once
// Node B: branch meter (INA226-B), relay for lamp 2, buzzer and OLED.

#define NODE_ID "B"
#define FW_TAG  "node-b 1.0"

const unsigned long SAMPLE_PERIOD_MS = 500;   // keep in step with sample_period_s in config.toml
const unsigned long POLL_PERIOD_MS   = 1000;  // how often the node asks the gateway for a command

const bool    HAS_INA    = false;              // false when this node has no INA226 fitted
const uint8_t INA_ADDR   = 0x40;              // tried first; the driver then scans 0x40-0x4F
const float   SHUNT_OHMS = 0.1f;
const int     SDA_PIN    = 21;
const int     SCL_PIN    = 22;
const uint8_t OLED_ADDR  = 0x3C;

const int RELAY_PIN  = 26;
const int BUZZER_PIN = 27;

// Set RELAY_ACTIVE_LOW to true if your relay board clicks on when the pin goes LOW.
// Test it with no lamp connected before you rely on this.
const bool RELAY_ACTIVE_LOW  = false;
const bool BUZZER_ACTIVE_LOW = true;          // for an active module that sounds while the pin is LOW

// A passive buzzer module needs a tone, not a level. Set BUZZER_PASSIVE to true for that kind.
const bool BUZZER_PASSIVE = false;
const int  BUZZER_FREQ = 2400;                // Hz, passive modules only
const unsigned long BEEP_ON_MS = 200;         // an alert beeps 200 ms in every second
const unsigned long BEEP_PERIOD_MS = 1000;
