// This code is a simplified version based on the ADS1256 library by Curious Scientist.
// It's modified to continuously read from a single, user-defined channel.

#include <ADS1256.h>

// --- IMPORTANT: CONFIGURE YOUR PINS AND BOARD HERE ---

// Platform-specific pin definitions (Leave this section as is)
#if defined(ARDUINO_ARCH_ESP32)
  #pragma message "Using ESP32"
  #pragma message "Using VSPI"
  #define USE_SPI SPI
#else // Default fallback for Arduino AVR, etc.
  #define USE_SPI SPI
#endif

/*
  This line creates the ADC object. You MUST configure it for your board.
  The parameters are: (DRDY_PIN, RESET_PIN, SYNC/PDWN_PIN, CS_PIN, VREF_IN_VOLTS, &SPI_BUS)
  Use 0 for pins you are not using (like RESET or SYNC).
*/
// The pin numbers here must match your physical wiring!
// ADS1256 adc(DRDY_PIN, RESET_PIN, SYNC_PIN, CS_PIN, ...);

ADS1256 adc(4, 2, 0, 5, 2.500, &USE_SPI);
long rawConversion = 0;  // Variable to store the raw 24-bit ADC value
float voltageValue = 0;  // Variable to store the human-readable voltage

void setup() {
  Serial.begin(115200); // Start serial communication
  while (!Serial) {
    ; // Wait for serial port to connect. Needed for native USB only
  }
  Serial.println("ADS1256 Single-Channel Test");

  // Initialize the ADC
  adc.InitializeADC();

  // --- Optional: Set Gain and Data Rate ---
  // You can change these default values if needed.
  adc.setPGA(PGA_1);                 // Set gain to 1x
  adc.setDRATE(DRATE_100SPS);        // Set data rate to 100 Samples Per Second
  
  Serial.println("Setup complete. Starting readings...");
  Serial.println("------------------------------------");
}


void loop() {
  // --- CHOOSE YOUR CHANNEL HERE ---
  int channelToRead = SING_0; // Reads from AIN0

  // Set the multiplexer to the desired channel
  adc.setMUX(channelToRead);

  // Read the raw value and convert it to voltage
  long rawConversion = adc.readSingle();
  float voltageValue = adc.convertToVoltage(rawConversion);

  // Print ONLY the voltage value for the Serial Plotter
  Serial.println(voltageValue);

  // The delay determines how fast the graph updates.
  // A smaller delay gives a faster, more detailed graph.
  delay(1);

}

