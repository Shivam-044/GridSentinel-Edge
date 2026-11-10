#pragma once
#include <Wire.h>

// Minimal INA226 driver. We only need the shunt and bus registers, so the
// calibration register is left alone and current is computed from the shunt voltage.
class INA226 {
 public:
  INA226(uint8_t addr, float shuntOhms) : addr_(addr), first_(addr), shunt_(shuntOhms) {}

  // Tries the configured address first, then 0x40-0x4F, because the address pads differ between modules.
  bool begin() {
    for (int i = -1; i < 16; i++) {
      addr_ = (i < 0) ? first_ : (uint8_t)(0x40 + i);
      if (read16(0xFE) != 0x5449) continue;     // manufacturer id, "TI"
      write16(0x00, 0x8000);                    // reset
      delay(2);
      write16(0x00, 0x4527);                    // 16 averages, 1.1 ms conversions, shunt + bus continuous
      return true;
    }
    addr_ = first_;
    return false;
  }
  uint8_t address() const { return addr_; }
  float busVolts()        { return read16(0x02) * 0.00125f; }
  float shuntMilliVolts() { return (int16_t)read16(0x01) * 0.0025f; }
  float amps()            { return shuntMilliVolts() / 1000.0f / shunt_; }

 private:
  uint8_t addr_, first_;
  float shunt_;

  void write16(uint8_t reg, uint16_t v) {
    Wire.beginTransmission(addr_);
    Wire.write(reg);
    Wire.write(v >> 8);
    Wire.write(v & 0xFF);
    Wire.endTransmission();
  }
  uint16_t read16(uint8_t reg) {
    Wire.beginTransmission(addr_);
    Wire.write(reg);
    Wire.endTransmission();               // full stop, then a separate read
    Wire.requestFrom(addr_, (uint8_t)2);
    if (Wire.available() < 2) return 0;
    uint16_t hi = Wire.read();
    return (hi << 8) | Wire.read();
  }
};
