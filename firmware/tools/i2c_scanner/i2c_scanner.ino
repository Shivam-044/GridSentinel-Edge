// Lists every device that answers on the I2C bus. Expect 0x40 (INA226) and, on Node B, 0x3C (OLED).
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  delay(500);
}

void loop() {
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("device at 0x%02X\n", addr);
      found++;
    }
  }
  if (!found) Serial.println("nothing found: check power, SDA (GPIO21), SCL (GPIO22) and the jumpers");
  Serial.println("--");
  delay(3000);
}
