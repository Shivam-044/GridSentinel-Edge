// GridSentinel Edge, Node A: measures the whole feeder and posts telemetry to the gateway.

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include "config.h"
#include "secrets.h"
#include "ina226.h"

INA226 ina(INA_ADDR, SHUNT_OHMS);
uint32_t seq = 0;
unsigned long lastSample = 0, lastWifiTry = 0;

// The ESP32 ADC is noisy, so average a batch of calibrated readings.
float readVsense() {
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(VSENSE_PIN);
  return (mv / 16.0f) / 1000.0f * VSENSE_RATIO * VSENSE_TRIM;
}

bool post(const String &body) {
  HTTPClient http;
  http.begin(String(GATEWAY_URL) + "/telemetry");
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(1500);
  int code = http.POST(body);
  http.end();
  return code == 200;
}

void sendSample() {
  float v = ina.busVolts();
  float i = ina.amps();
  float vs = readVsense();

  JsonDocument doc;
  doc["node_id"]   = NODE_ID;
  doc["seq"]       = ++seq;                 // advances even when the post fails, so gaps show up
  doc["uptime_ms"] = millis();
  doc["bus_v"]     = serialized(String(v, 3));
  doc["current_a"] = serialized(String(i, 4));
  doc["power_w"]   = serialized(String(v * i, 3));
  doc["vsense_v"]  = serialized(String(vs, 3));
  doc["rssi"]      = WiFi.RSSI();
  doc["fw"]        = FW_TAG;

  String body;
  serializeJson(doc, body);
  bool ok = (WiFi.status() == WL_CONNECTED) && post(body);
  Serial.printf("%s seq=%lu  %.3f V  %.4f A  vs=%.3f V  %s\n", NODE_ID, (unsigned long)seq, v, i, vs, ok ? "sent" : "not sent");
}

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);
  analogSetPinAttenuation(VSENSE_PIN, ADC_11db);

  if (ina.begin()) Serial.printf("INA226 found at 0x%02X\n", ina.address());
  else Serial.println("INA226 not answering. Check VCC, GND, SDA, SCL and the solder joints.");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(250);
  Serial.println(WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : "Wi-Fi not connected yet, will keep trying");
}

void loop() {
  unsigned long now = millis();
  if (WiFi.status() != WL_CONNECTED && now - lastWifiTry > 5000) {
    lastWifiTry = now;
    WiFi.reconnect();
  }
  if (now - lastSample >= SAMPLE_PERIOD_MS) {
    lastSample = now;
    sendSample();
  }
}
