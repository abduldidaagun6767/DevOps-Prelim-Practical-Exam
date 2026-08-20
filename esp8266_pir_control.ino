/*
  ESP8266 (or ESP-01) -> Flask IoT Dashboard
  ------------------------------------------
  - Reads a PIR motion sensor
  - POSTs the reading to /api/sensor
  - Reads the device_state ("ON"/"OFF") from the response
  - Drives an output device (LED / relay) accordingly

  Required libraries (Arduino IDE -> Library Manager):
    - ESP8266WiFi (comes with ESP8266 board package)
    - ESP8266HTTPClient (comes with ESP8266 board package)
    - ArduinoJson (by Benoit Blanchon)

  Board package URL (Arduino IDE -> Preferences -> Additional Boards Manager URLs):
    http://arduino.esp8266.com/stable/package_esp8266com_index.json
*/

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

// ---------------- CONFIG ----------------
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_HOST   = "http://192.168.1.50:5000"; // or https://your-app.onrender.com

// --- Pin setup ---
// ESP-01 only exposes GPIO0 and GPIO2 as free GPIOs. Both are also
// "boot strapping" pins, so keep the PIR sensor from holding GPIO0 LOW
// at power-on, or the board may enter flash mode instead of booting normally.
const int PIR_PIN = 0;   // GPIO0 <- PIR OUT
const int LED_PIN = 2;   // GPIO2 -> LED / relay IN

// If you're using a NodeMCU / Wemos D1 Mini instead (recommended if you
// want easier wiring / no boot-pin conflicts), use labeled pins instead, e.g.:
// const int PIR_PIN = D5;
// const int LED_PIN = D6;

unsigned long lastPoll = 0;
const unsigned long POLL_INTERVAL_MS = 1500;

bool serverUsesHttps() {
  return String(SERVER_HOST).startsWith("https://");
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Connected! IP: " + WiFi.localIP().toString());
}

String parseDeviceState(const String& responseBody) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, responseBody);

  if (err) {
    Serial.println("JSON parse failed: " + String(err.c_str()));
    return "";
  }

  if (doc["device_state"].is<String>()) {
    return doc["device_state"].as<String>();
  }

  return "";
}

String getDeviceStateFromServer() {
  HTTPClient http;
  String url = String(SERVER_HOST) + "/api/state";

  if (serverUsesHttps()) {
    WiFiClientSecure client;
    client.setInsecure();
    if (!http.begin(client, url)) {
      Serial.println("Failed to start HTTPS device-state request");
      return "";
    }
    int httpCode = http.GET();
    if (httpCode == HTTP_CODE_OK) {
      String response = http.getString();
      http.end();
      return parseDeviceState(response);
    }
    Serial.println("GET /api/state failed, HTTP code: " + String(httpCode));
    http.end();
    return "";
  }

  WiFiClient client;
  if (!http.begin(client, url)) {
    Serial.println("Failed to start HTTP device-state request");
    return "";
  }

  int httpCode = http.GET();
  if (httpCode == HTTP_CODE_OK) {
    String response = http.getString();
    http.end();
    return parseDeviceState(response);
  }

  Serial.println("GET /api/state failed, HTTP code: " + String(httpCode));
  http.end();
  return "";
}

// POST the PIR reading to /api/sensor and return the device_state from the reply.
// If the server does not return a device_state, fall back to /api/state.
String sendReading(int motion) {
  HTTPClient http;
  String url = String(SERVER_HOST) + "/api/sensor";
  String payload = "{\"motion\":" + String(motion) + "}";

  if (serverUsesHttps()) {
    WiFiClientSecure client;
    client.setInsecure();
    if (!http.begin(client, url)) {
      Serial.println("HTTP begin failed for HTTPS sensor post");
      return getDeviceStateFromServer();
    }
    http.addHeader("Content-Type", "application/json");
    int httpCode = http.POST(payload);

    String deviceState = "";
    if (httpCode == HTTP_CODE_OK) {
      deviceState = parseDeviceState(http.getString());
      Serial.println("motion=" + String(motion) + " -> device_state=" + deviceState);
    } else {
      Serial.println("POST failed, HTTP code: " + String(httpCode));
      deviceState = getDeviceStateFromServer();
    }

    http.end();
    return deviceState;
  }

  WiFiClient client;
  if (!http.begin(client, url)) {
    Serial.println("HTTP begin failed for HTTP sensor post");
    return getDeviceStateFromServer();
  }

  http.addHeader("Content-Type", "application/json");
  int httpCode = http.POST(payload);

  String deviceState = "";
  if (httpCode == HTTP_CODE_OK) {
    deviceState = parseDeviceState(http.getString());
    Serial.println("motion=" + String(motion) + " -> device_state=" + deviceState);
  } else {
    Serial.println("POST failed, HTTP code: " + String(httpCode));
    deviceState = getDeviceStateFromServer();
  }

  http.end();
  return deviceState;
}

void applyDeviceState(const String& deviceState) {
  if (deviceState == "ON") {
    digitalWrite(LED_PIN, HIGH);
  } else if (deviceState == "OFF") {
    digitalWrite(LED_PIN, LOW);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (millis() - lastPoll >= POLL_INTERVAL_MS) {
    lastPoll = millis();

    int motion = digitalRead(PIR_PIN);
    String deviceState = sendReading(motion);
    applyDeviceState(deviceState);
  }
}
