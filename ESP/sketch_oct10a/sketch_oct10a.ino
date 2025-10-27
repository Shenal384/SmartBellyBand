#include <ADS1256.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiUdp.h>

// ---------------- WiFi Settings ----------------
const char* ssid     = "YOUR_WIFI_SSID";     // <-- change
const char* password = "YOUR_WIFI_PASSWORD"; // <-- change
const char* hostIP   = "192.168.1.100";      // <-- your PC IP
const int udpPort    = 5005;

WiFiUDP udp;

// ---------------- ADS1256 Pins -----------------
const int DRDY_PIN  = 15;
const int RESET_PIN = 2;
const int SYNC_PIN  = 14;
const int CS_PIN    = 5;
const float VREF    = 2.5;

// Create ADS1256 object
ADS1256 A(DRDY_PIN, RESET_PIN, SYNC_PIN, CS_PIN, VREF, &SPI);

// ---------------- Batch Settings ---------------
const int BATCH_SIZE = 20;
float batch[BATCH_SIZE];
int batchCount = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Connect Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected.");
  Serial.print("ESP32 IP: "); Serial.println(WiFi.localIP());
  udp.begin(udpPort);

  // Init ADS1256
  SPI.begin();
  A.InitializeADC();
  A.setPGA(PGA_1);
  A.setMUX(SING_0);             // AIN0 single-ended
  A.setDRATE(DRATE_500SPS);     // 500 samples/sec
  Serial.println("ADS1256 ready. Streaming in batches...");
}

void loop() {
  long raw = A.readSingle();
  float volts = A.convertToVoltage(raw);

  // Collect samples into buffer
  batch[batchCount++] = volts;

  // When full, send as CSV string
  if (batchCount >= BATCH_SIZE) {
    String packet = "";
    for (int i = 0; i < BATCH_SIZE; i++) {
      packet += String(batch[i], 6) + ",";
    }

    udp.beginPacket(hostIP, udpPort);
    udp.print(packet);
    udp.endPacket();

    batchCount = 0; // reset buffer
  }

  delay(2); // pacing ~500 SPS
}
