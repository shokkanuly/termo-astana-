/**
 * TermoAstana ESP32 IoT Client (v3.0)
 * 
 * Hardware requirements:
 *  - ESP32 board
 *  - 2x DS18B20 temperature sensors (inside & outside)
 *  - 1x Magnetic/Button reed switch (window state detection)
 *  - 1x 4.7k Ohm pull-up resistor between DS18B20 Data pin and VCC (3.3V)
 * 
 * Libraries:
 *  - WiFiManager by tzapu (install via Arduino Library Manager)
 *  - DallasTemperature by Miles Burton
 *  - OneWire by Paul Stoffregen
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <WiFiManager.h> // Non-hardcoded WiFi configuration portal

// Hardware Pin configuration
#define ONE_WIRE_BUS 4        // DS18B20 Data pin connected to GPIO 4
#define WINDOW_SWITCH_PIN 15  // Reed switch or button connected to GPIO 15 (pull-up)

// Target FastAPI backend URL (Adjust IP of host running backend on local network)
const char* serverUrl = "http://192.168.1.100:8000/api/v1/esp32/telemetry";

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// Timing variables for non-blocking execution (avoid delay())
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 5000; // Telemetry post every 5 seconds

void setup() {
  Serial.begin(115200);
  
  // Set up inputs
  pinMode(WINDOW_SWITCH_PIN, INPUT_PULLUP);
  
  // Initialize DS18B20 sensors
  sensors.begin();
  
  Serial.println("\nInitializing WiFiManager...");
  WiFiManager wm;
  
  // Custom access point for network configuration via captive portal (e.g. from phone)
  bool res = wm.autoConnect("TermoAstana_ESP32_Config", "astana123");
  
  if (!res) {
    Serial.println("WiFi configuration failed. Restarting ESP32...");
    ESP.restart();
  } else {
    Serial.print("WiFi Connected! IP Address: ");
    Serial.println(WiFi.localIP());
  }
}

void loop() {
  unsigned long currentMillis = millis();
  
  // Run telemetry task every interval (non-blocking)
  if (currentMillis - lastSendTime >= sendInterval) {
    lastSendTime = currentMillis;
    
    // Check WiFi connection status
    if (WiFi.status() == WL_CONNECTED) {
      sendTelemetry();
    } else {
      Serial.println("WiFi Disconnected. Reconnecting automatically...");
    }
  }
}

void sendTelemetry() {
  // Request readings from DS18B20 sensors
  sensors.requestTemperatures();
  
  // Sensor 0 = Inside Temperature, Sensor 1 = Outside Temperature
  float t_in = sensors.getTempCByIndex(0);
  float t_out = sensors.getTempCByIndex(1);
  
  // Check if sensors are connected (DS18B20 returns -127 if disconnected or missing pull-up resistor)
  if (t_in == DEVICE_DISCONNECTED_C || t_out == DEVICE_DISCONNECTED_C) {
    Serial.println("Error: DS18B20 sensors disconnected or pull-up resistor missing!");
    // Fallback or skip to avoid sending corrupt values
    return;
  }
  
  // Read window state (low = closed, high = open - depending on wiring)
  // We assume switch pull-up: normal closed = LOW, open = HIGH
  bool windowOpen = digitalRead(WINDOW_SWITCH_PIN) == HIGH;
  
  // Construct JSON payload
  String jsonPayload = "{";
  jsonPayload += "\"node_id\":\"esp32_hw_01\",";
  jsonPayload += "\"t_in\":" + String(t_in, 1) + ",";
  jsonPayload += "\"t_out\":" + String(t_out, 1) + ",";
  jsonPayload += "\"window_open\":" + String(windowOpen ? "true" : "false");
  jsonPayload += "}";
  
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  
  Serial.print("Sending telemetry POST: ");
  Serial.println(jsonPayload);
  
  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.print("Response Code: ");
    Serial.println(httpResponseCode);
    Serial.print("Server Reply: ");
    Serial.println(response);
  } else {
    Serial.print("Error sending POST request. Error code: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}
