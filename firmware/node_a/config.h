#pragma once
// Node A: feeder meter (INA226-A) and the 0-25 V voltage sensor.

#define NODE_ID "A"
#define FW_TAG  "node-a 1.0"

const unsigned long SAMPLE_PERIOD_MS = 500;   // keep in step with sample_period_s in config.toml

const uint8_t INA_ADDR   = 0x40;              // tried first; the driver then scans 0x40-0x4F
const float   SHUNT_OHMS = 0.1f;              // the R100 resistor on the module
const int     SDA_PIN    = 21;
const int     SCL_PIN    = 22;

const int   VSENSE_PIN   = 34;                // S pin of the voltage sensor, ADC1 channel
const float VSENSE_RATIO = 5.0f;              // divider ratio of the module
const float VSENSE_TRIM  = 1.0f;              // set after comparing with a multimeter at 12 V
