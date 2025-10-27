
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ADS1256.h>

// ---------- WiFi Settings ----------
const char* ssid = "Wi-Fi 775377 2.4G";
const char* password = "UE6sftRQ";
const char* hostIP = "192.168.20.15"; // PC IP running Python listener
const int udpPort = 5005;
WiFiUDP udp;

// ---------- ADS1256 Settings ----------
#define DRDY_PIN 4
#define RESET_PIN 2
#define SYNC_PIN 0
#define CS_PIN 5
#define VREF 2.5

ADS1256 A(DRDY_PIN, RESET_PIN, SYNC_PIN, CS_PIN, VREF, &SPI);

// ---------- Sampling & Transmission ----------
const int FS = 500;          // Sampling rate (SPS)
const int BATCH_SIZE = 50;   // Samples per UDP packet
float sampleBuffer[BATCH_SIZE];
int sampleCount = 0;

// ---------- Setup ----------
void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("ESP32 IP: "); Serial.println(WiFi.localIP());

  SPI.begin();
  A.InitializeADC();
  A.setPGA(PGA_1);
  A.setDRATE(DRATE_500SPS);
  A.setMUX(SING_0);

  Serial.println("ADS1256 initialized (CH0, 500SPS)");
}

// ---------- Loop ----------
void loop() {
  // Wait for data ready
  while (digitalRead(DRDY_PIN) == HIGH);

  // Read sample
  long raw = A.readSingle();
  float volts = A.convertToVoltage(raw);

  // Store in buffer
  sampleBuffer[sampleCount++] = volts;

  // If buffer full, send as binary
  if (sampleCount >= BATCH_SIZE) {
    udp.beginPacket(hostIP, udpPort);
    udp.write((uint8_t*)sampleBuffer, sizeof(sampleBuffer));
    udp.endPacket();
    sampleCount = 0;
  }
}

