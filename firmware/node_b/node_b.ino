// GridSentinel Edge, Node B: measures the switched branch, drives the relay, buzzer and OLED.

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"
#include "secrets.h"
#include "ina226.h"

INA226 ina(INA_ADDR, SHUNT_OHMS);
Adafruit_SSD1306 oled(128, 64, &Wire, -1);

uint32_t seq = 0;
bool relayOn = false, buzzerOn = false, oledOk = false;
unsigned long lastSample = 0, lastPoll = 0, lastDraw = 0, lastWifiTry = 0;
float lastV = 0, lastI = 0;
char alertText[24] = "";

void setRelay(bool on)  { relayOn = on;  digitalWrite(RELAY_PIN,  (on != RELAY_ACTIVE_LOW)  ? HIGH : LOW); }
// sound = true makes noise right now. A passive module gets a tone, an active one a level.
void driveBuzzer(bool sound) {
  if (BUZZER_PASSIVE) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWriteTone(BUZZER_PIN, sound ? BUZZER_FREQ : 0);
#else
    ledcWriteTone(0, sound ? BUZZER_FREQ : 0);
#endif
  } else {
    digitalWrite(BUZZER_PIN, (sound != BUZZER_ACTIVE_LOW) ? HIGH : LOW);
  }
}
void setBuzzer(bool on) { buzzerOn = on; if (!on) driveBuzzer(false); }
void updateBuzzer() { if (buzzerOn) driveBuzzer((millis() % BEEP_PERIOD_MS) < BEEP_ON_MS); }

bool post(const String &path, const String &body) {
  HTTPClient http;
  http.begin(String(GATEWAY_URL) + path);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(1500);
  int code = http.POST(body);
  http.end();
  return code == 200;
}

void sendSample() {
  lastV = HAS_INA ? ina.busVolts() : 0.0f;
  lastI = HAS_INA ? ina.amps() : 0.0f;

  JsonDocument doc;
  doc["node_id"]   = NODE_ID;
  doc["seq"]       = ++seq;
  doc["uptime_ms"] = millis();
  doc["bus_v"]     = serialized(String(lastV, 3));
  doc["current_a"] = serialized(String(lastI, 4));
  doc["power_w"]   = serialized(String(lastV * lastI, 3));
  doc["relay_on"]  = relayOn;
  doc["rssi"]      = WiFi.RSSI();
  doc["fw"]        = FW_TAG;

  String body;
  serializeJson(doc, body);
  bool ok = (WiFi.status() == WL_CONNECTED) && post("/telemetry", body);
  Serial.printf("%s seq=%lu  %.3f V  %.4f A  relay=%d  %s\n", NODE_ID, (unsigned long)seq, lastV, lastI, relayOn, ok ? "sent" : "not sent");
}

void pollCommand() {
  if (WiFi.status() != WL_CONNECTED) return;
  int id = 0;
  String cmd, text;

  HTTPClient http;
  http.begin(String(GATEWAY_URL) + "/command/" + NODE_ID);
  http.setTimeout(1000);
  if (http.GET() == 200) {
    JsonDocument d;
    if (!deserializeJson(d, http.getString())) {
      id   = d["id"] | 0;
      cmd  = d["command"] | "none";
      text = d["text"] | "";
    }
  }
  http.end();
  if (id == 0) return;

  if      (cmd == "relay_on")   setRelay(true);
  else if (cmd == "relay_off")  setRelay(false);
  else if (cmd == "buzzer_on")  { setBuzzer(true);  text.toCharArray(alertText, sizeof(alertText)); }
  else if (cmd == "buzzer_off") { setBuzzer(false); alertText[0] = 0; }
  post("/command/" + String(id) + "/ack", "{}");
}

void draw() {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);  oled.print("GridSentinel  Node B");
  oled.setCursor(0, 12); oled.print(WiFi.status() == WL_CONNECTED ? "Link: ok" : "Link: down");
  oled.setCursor(0, 24);
  if (HAS_INA) oled.printf("%.2f V   %.3f A", lastV, lastI);
  else         oled.print("Branch meter: none");
  oled.setCursor(0, 36); oled.print(relayOn ? "Lamp 2: on" : "Lamp 2: off");
  oled.setCursor(0, 48); oled.print(alertText[0] ? alertText : "Status: normal");
  oled.display();
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  if (BUZZER_PASSIVE) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach(BUZZER_PIN, BUZZER_FREQ, 8);
#else
    ledcSetup(0, BUZZER_FREQ, 8);
    ledcAttachPin(BUZZER_PIN, 0);
#endif
  } else {
    pinMode(BUZZER_PIN, OUTPUT);
  }
  setRelay(false);                       // lamp 2 starts off
  setBuzzer(false);

  Wire.begin(SDA_PIN, SCL_PIN);
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (!oledOk) Serial.println("OLED not found at 0x3C");
  if (HAS_INA) {
    if (ina.begin()) Serial.printf("INA226 found at 0x%02X\n", ina.address());
    else Serial.println("INA226 not answering. Check VCC, GND, SDA, SCL and the solder joints.");
  }

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
  if (now - lastSample >= SAMPLE_PERIOD_MS) { lastSample = now; sendSample(); }
  if (now - lastPoll   >= POLL_PERIOD_MS)   { lastPoll = now;   pollCommand(); }
  if (now - lastDraw   >= 500)              { lastDraw = now;   draw(); }
  updateBuzzer();
}
