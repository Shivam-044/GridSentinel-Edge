// Prints raw INA226 readings once a second. Use it to prove the sensor works before the full node sketch.
#include <Wire.h>
#include "ina226.h"

INA226 ina(0x40, 0.1f);

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  delay(500);
  if (ina.begin()) Serial.printf("INA226 found at 0x%02X\n", ina.address());
  else Serial.println("INA226 not answering at any address from 0x40 to 0x4F");
}

void loop() {
  Serial.printf("bus %.3f V   shunt %.3f mV   current %.4f A\n", ina.busVolts(), ina.shuntMilliVolts(), ina.amps());
  delay(1000);
}
