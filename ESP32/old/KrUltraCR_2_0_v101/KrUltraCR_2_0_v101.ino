/*******************************************************************************************
 * KrUltraCR 2.0.100
 * 
 * Checkpoint Registration system
 * By Torgeir Kruke (C) 2023
 *******************************************************************************************/


// **************************************    INIT     *************************************

// Kompilatordirektiver og variabeldeklarasjoner
#include <FastLED.h>
#include <Preferences.h>
#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include <addons/TokenHelper.h>
#include <addons/RTDBHelper.h>
#include "Credentials.h"
#include "RingBuffer.h"
#include "Timer.h"

// Debug
String debugMessage = "";

// ESP32 spesifikk konfig
#define cpuFrequency 80       // Sett klokkefrekvens til 80 for å spare strøm
Preferences preferences;      // Brukes for å finne antall boot-sekvenser som er kjørt
String rfid_reader_chip_id = String(ESP.getEfuseMac()); // Hent chip-ID
// const int interruptPin =22;   // D22 = GPIO22 på ESP32 - koblet til RST på RC522
// const int maxSleep = 30;      // max sekunder i LightSleep-mode før den våkner
// RTC_DATA_ATTR int wakeCause = 0;  // global variabel for å lagre interrupt-årsak
// RTC_DATA_ATTR uint64_t timeAsleep = 10000;  // lagres i RTC-minnet (Real Time Clock memory) som bevares gjennom DeepSleep-modus hvis det brukes

// For kommunikasjon med RC522 og lesing av rfid-brikker
#define SS_PIN 5
#define RST_PIN 0
MFRC522 rfid(SS_PIN, RST_PIN);  // Instance of the class
MFRC522::MIFARE_Key key;
RingBuffer ringBuffer;
RingBuffer::RFIDTag nuidPICC = RingBuffer::createRFIDTag();  // Variable that will store new NUID before adding it to the ring buffer

// Timere, bl.a. for å oppnå asynkron prosess for wifi-oppkobling
const int MAX_TIMERS = 5; // Antall timerobjekter - utvides etter behov (NB: Sjekk ut om bruk av timer.h er bedre)
// #define timOn 0   // timer for å timestampe rfid-registreringer
// #define timWifiConn 1
// const unsigned long maxWifiConnTime = 60000;      // millisekunder
// #define timAwaitWifiRetry 2
// const unsigned long awaitWifiRetryTime = 300000;   // millisekunder
// #define timTick 3
// const unsigned long tickTime = 1000;   // millisekunder
#define timLastTagRead 4
Timer timers[MAX_TIMERS]; // Array for timerobjekter
int64_t sleepStartTime;   // For bruk av ESP32 sin real time clock (RTC)

// For Firebase Realtime Database
FirebaseData fbdo;  // FirebaseData fbdo; i eksempel
FirebaseConfig config;  // FirebaseConfig config; i eksempel
FirebaseAuth auth;  // FirebaseAuth auth; i eksempel
int rfid_reader_id = 2; // rfid-leser med defaultverdier (test)
int checkpoint_id = 0;
String rfid_reader_name = "Test location 1";
int event_id = 0;
int status = 0;
int minimum_split = 5000;   //     minimum tid mellom lesing av samme rfid-tag i millisekunder (default 5000 = 5 sekunder)
bool default_parameters = true;  // flagg som varsler at minimum_split og andre parametre ikke er lest fra db ennå
// -> se Credentials.h for øvrige parametre for oppkobling mot Firebase-databasen

// For bruk av multithreading
SemaphoreHandle_t xMutex = NULL;  // Create a mutex object - for å sikre at ringBuffer ikke oppdateres samtidig av dbBuffer() og loop()

// For WiFi
bool wifiInitiated = false;
// -> se Credentials.h for øvrige parametre for wifi-oppkobling

// For LED håndtering
#define NUM_LEDS 3
#define DATA_PIN 4
CRGB leds[NUM_LEDS];


// *************************************    FUNCTIONS      *******************************************************

/**
 * Funksjon som oppdaterer databasen med rfid-registreringer fra ringbufferet
 */

/**
 * Funksjon som forsøker å koble til wifi
 */
bool wifiConnect() {
  WiFi.begin(default_wifi_ssid, default_wifi_password);
  // Auto reconnect is set true as default
  // To set auto connect off, use the following function
  //    WiFi.setAutoReconnect(false);

  // Will try for about 10 seconds (20 x 500ms)
  int tryDelay = 500;
  int numberOfTries = 20;

  // Wait for the WiFi event
  while (true) {

    switch (WiFi.status()) {
      case WL_NO_SSID_AVAIL:
        Serial.println("[WiFi] SSID not found");
        break;
      case WL_CONNECT_FAILED:
        Serial.print("[WiFi] Failed - WiFi not connected! Reason: ");
        return false;
        break;
      case WL_CONNECTION_LOST:
        Serial.println("[WiFi] Connection was lost");
        break;
      case WL_SCAN_COMPLETED:
        Serial.println("[WiFi] Scan is completed");
        break;
      case WL_DISCONNECTED:
        Serial.println("[WiFi] WiFi is disconnected");
        break;
      case WL_CONNECTED:
        Serial.println("[WiFi] WiFi is connected!");
        Serial.print("[WiFi] IP address: ");
        Serial.println(WiFi.localIP());
        return true;
        break;
      default:
        Serial.print("[WiFi] WiFi Status: ");
        Serial.println(WiFi.status());
        break;
    }
    delay(tryDelay);

    if (numberOfTries <= 0) {
      Serial.print("[WiFi] Failed to connect to WiFi!");
      // This function will disconnect and turn off the WiFi (NVS WiFi data is kept)
      if (WiFi.disconnect(true, false)) {
        Serial.println(F("[WiFi] Disconnected from WiFi!"));
      }
      return false;
    } else {
      numberOfTries--;
    }
  }
}

/**
 * getParameters()
 *
 * Funksjon som henter parametre fra databasen
 * Returnerer true hvis operasjonen går bra, og false hvis det oppstår en feil
 *    minimum_split er den minste tiden som godtas for at et rfid-kort skal kunne registreres på nytt
 *    checkpoint_id er identifikator for sjekkpunktet som rfid-leseren er tilordnet
 *    rfid_reader_name er kort-navn for sjekkpunktet som rfid-leseren er tilordnet
 *    event_id er identifikator for arrangementet som rfid-leseren er tilordnet
 *    rfid_reader_id er identifikator for rfid-leseren = indeks i arrayet rfid_readers
 *    rfid_reader_chip_id er MAC-adressen til mikrokontrolleren som sitter i rfid-leseren (ESP32) - ikke å forveksle med selve rfid-leseren (RC522) 
 */
bool getParameters() {
  Serial.println(F("Starter getParameters"));
  
  if (!WiFi.isConnected()) {
    Serial.println(F("No wifi - skip getParameters"));
  return false; 
  }

  if (Firebase.ready() && Firebase.RTDB.getArray(&fbdo, "/rfid_readers")) {
    FirebaseJsonArray &readersArray = fbdo.jsonArray();

    Serial.println("readersArray.size = " + String(readersArray.size()));

    for (size_t i = 0; i < readersArray.size(); i++) {
      Serial.print("Reading array index: " + String(i) + " - ");
      
      FirebaseJsonData jsonData;
      // Først, få tak i hele JSON-objektet ved det aktuelle indeksen.
      if (readersArray.get(jsonData, i)) {
        // Konverterer den hentede dataen til et FirebaseJson-objekt.
        FirebaseJson readerObject;
        readerObject.setJsonData(jsonData.stringValue.c_str());
        
        FirebaseJsonData chipData;
        if (readerObject.get(chipData, "chip_id")) {
          String retrieved_chip_id = chipData.stringValue;
          Serial.print("Chip ID " + retrieved_chip_id);
            if (retrieved_chip_id != rfid_reader_chip_id) {
              Serial.println("no match");
            } else {
              Serial.println("***  MATCH!  ***");
              rfid_reader_id = i;
              
              // Hente checkpoint_id
              FirebaseJsonData checkpointData;
              if (readerObject.get(checkpointData, "checkpoint_id")) {
                  checkpoint_id = checkpointData.intValue;
                  Serial.println("checkpoint_id: " + String(checkpoint_id));
              }
              
              // Hente name (som vil bli lagret i rfid_reader_name)
              FirebaseJsonData nameData;
              if (readerObject.get(nameData, "name")) {
                  rfid_reader_name = nameData.stringValue.c_str();
                  Serial.println("rfid_reader_name: " + rfid_reader_name);
              }
              
              // Hente event_id
              FirebaseJsonData eventData;
              if (readerObject.get(eventData, "event_id")) {
                  event_id = eventData.intValue;
                  Serial.println("event_id: " + String(event_id));
              }
              
              // Hente minimum_split, hvis den eksisterer
              FirebaseJsonData minSplitData;
              if (readerObject.get(minSplitData, "minimum_split")) {
                  minimum_split = minSplitData.intValue;
                  Serial.println("minimum_split: " + String(minimum_split));
              } 

              // Avbryt løkken siden vi har funnet og behandlet riktig chip_id
              default_parameters = false;
              return true;                
              break;
            }
        } else {
          Serial.println("Failed to get chip_id at index " + String(i));
          return false;
        }
      } else {
        Serial.println("Failed to get JSON object at index " + String(i));
        return false;
      }
    }
  } else {
      Serial.println("Feil ved henting av data: " + fbdo.errorReason());
      return false;
  }
}

/**
 * dbUpdate()
 *
 * Kjører i evig løkke på core 0 som en slags loop2()
 * Venter på at det skal komme inn nye rfid-registreringer 
 * Når ringBuffer har minst en rfid-registrering så oppdaterer den databasen
 * Forutsetter internettforbindelse (wifi) og at databasen er tilgjengelig (Firebase Real Time Database)
 * Bruker mutex (xMutex) for å forsikre at oppdateringer av ringBuffer ikke kommer i konflikt med oppdateringer som gjøres i loop()
 */
void dbUpdate(void *pvParameters) { Serial.println("dbUpdate startet på core 0"); while (true) {
  
  // Serial.println("ringBuffer.count = " + String(ringBuffer.count()));
  // Serial.println("Wifi: " + WiFi.isConnected() ? "Connected" : "Not connected" );
  // Serial.println("Firebase: " + Firebase.ready() ? "Ready" : "Not ready");
  if (ringBuffer.count() > 0 && WiFi.isConnected() && Firebase.ready()) {       // Elementer i kø som skal overføres til databasen
    leds[1] = CRGB::Yellow;
    FastLED.show();
    Serial.println("Antall registreringer i buffer: " + String(ringBuffer.count()));
    RingBuffer::RFIDTag oldestTag;
    String tagStr = "";
    int reg_delay_ms = 0;
    Serial.print("dbUpdate ber om xMutex... ");
    if (xSemaphoreTake (xMutex, portMAX_DELAY)) {
      Serial.print("dbUpdate tok xMutex...");
      leds[1] = CRGB::Blue;
      FastLED.show();
      oldestTag = ringBuffer.getOldest();
      Serial.println("Hentet eldste tag fra ringbuffer");
      tagStr = ringBuffer.getTagAsStr(oldestTag);
      reg_delay_ms = millis() - oldestTag.timestamp;
      xSemaphoreGive (xMutex);  // release the mutex
      Serial.println("dbUpdate ga tilbake xMutex");
    }

    // Serial.println("tar en 5 sekunders pause for å teste registrering av tags mens dbUpdate er aktiv");
    // delay(5000);

    // Oppretter FirebaseJson-objektet som skal lagres
    FirebaseJson registration;
    registration.set("rfid_tag_uid", tagStr);
    registration.set("reg_delay_ms", reg_delay_ms);
    registration.set("rfid_reader_id", rfid_reader_id);
    registration.set("rfid_reader_chip_id", rfid_reader_chip_id);
    registration.set("checkpoint_id", checkpoint_id);
    registration.set("rfid_reader_name", rfid_reader_name);
    registration.set("event_id", event_id);

    // Push data til Firebase under /registrations
    if (!Firebase.RTDB.pushJSON(&fbdo, "/registrations", &registration)) {
        Serial.println("Error sending registration: " + fbdo.errorReason());
        leds[1] = CRGB::Red;
        FastLED.show();
    } else {
        Serial.print("Registrering lagt til i databasen. ");
        leds[1] = CRGB::Green;
        FastLED.show();
        String uniqueKey = fbdo.pushName();   // Hent den unike nøkkelen generert av push-operasjonen
        // Serial.println("Unique key generated by push: " + uniqueKey);
        String path = "/registrations/" + uniqueKey + "/timestamp";   // Bruk denne unike nøkkelen for å bygge stien for tidsstempelet
        // Serial.println("Trying to set timestamp at: " + path);
        if (!Firebase.RTDB.setTimestamp(&fbdo, path.c_str())) {
            Serial.println("Failed to set timestamp: " + fbdo.errorReason());
            leds[1] = CRGB::Black;
            FastLED.show();
        } else {
            Serial.println("Timestamp lagt til registreringen.");
        }
        if (xSemaphoreTake (xMutex, portMAX_DELAY)) {
          ringBuffer.removeOldest();  // skriving til db gikk ok - fjern fra ringbuffer
          xSemaphoreGive (xMutex);  // release the mutex
          Serial.println("One RFIDTag removed from ring buffer!");
        }
    }
    delay (500); // la lyset stå lenge nok til at det kan sees
    leds[1] = CRGB::Black;
    FastLED.show();

  } else {
    Serial.print(".");
    delay (1000);   // vent litt før vi sjekker om det har kommet nye registreringer (ikke bråhast)
  }
} }



// *****************************************    SETUP     ***********************************************************
void setup() {

  Serial.begin(115200);
  while (!Serial && millis() < 5000);  // wait for Serial to connect
  Serial.println("Start Setup()");

  FastLED.addLeds<WS2812, DATA_PIN, GRB>(leds, NUM_LEDS);
  leds[0] = CRGB::Green;
  leds[1] = CRGB::Blue;
  leds[2] = CRGB::Yellow;
  FastLED.show();

  Serial.print("rfid_reader_chip_id = ");
  Serial.println(rfid_reader_chip_id); 

  // setCpuFrequencyMhz(cpuFrequency);     // juster ned cpu-frekvensen for å redusere strømforbruket

  // Les antall ganger oppstart har skjedd - kan lagres sammen med tid for å ta hensyn til at tiden blir nullstilt hver gang det bootes
  preferences.begin("KrUltraCR", false);   // Open Preferences with KrUltraCR namespace (max 15 char).
  unsigned int startCounter = preferences.getUInt("KrUltraCRcount", 0);
  // Serial.printf("Previous counter value: %u\n", startCounter);
  startCounter++;
  // Serial.printf("Current counter value: %u\n", startCounter);
  preferences.putUInt("KrUltraCRcount", startCounter);    // Store the counter to the Preferences
  startCounter = preferences.getUInt("KrUltraCRcount", 0);
  Serial.printf("Boot counter: %u\n", startCounter);
  preferences.end();                          // Close the Preferences

  // Start wifi
  if (wifiConnect()) {
    wifiInitiated = true;
    Serial.println(F("WiFi connected"));
    leds[1] = CRGB::Green;
    FastLED.show();
  };

  // Initialiser Firebase RTDB
  Serial.printf("Firebase Client v%s\n\n", FIREBASE_CLIENT_VERSION);
  config.database_url = FIREBASE_DATABASE_URL;
  config.api_key = FIREBASE_API_KEY;
  auth.user.email = FIREBASE_USER_EMAIL;
  auth.user.password = FIREBASE_USER_PASSWORD;
  config.token_status_callback = tokenStatusCallback; // see addons/TokenHelper.h

  // Koble til Firebase
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  // Koble opp mot databasen og hent parametre
  if (WiFi.isConnected()) {
     if (Firebase.ready()) {
      Serial.println(F("Firebase ready!"));
      if (getParameters()) {
        Serial.println("Updated parameters");
        leds[2] = CRGB::Green;
        FastLED.show();
      } else {
        Serial.println(F("Unable to read parameters - keeping default values"));
      }
    }
  } else {
      Serial.println(F("Unable to read parameters - keeping default values"));
      wifiInitiated = false;
  }

  // Start kommunikasjon med RC522
  SPI.begin();      // Init SPI bus
  rfid.PCD_Init();  // Init MFRC522
  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }
  Serial.println(F("This code scan the MIFARE Classsic NUID."));

  xMutex = xSemaphoreCreateMutex();  // crete a mutex object

  xTaskCreatePinnedToCore (         // definerer at dbUpdate skal kjøre på core 0
    dbUpdate,     // Function to implement the task
    "dbUpdate",   // Name of the task
    8000,      // Stack size in words. 10000 ok, 5000 for lite
    NULL,      // Task input parameter
    10,         // Priority of the task
    NULL,      // Task handle.
    0          // Core where the task should run
  );

  delay(1000);  // la led-lampene lyse litt før de slås av
  FastLED.clear();
  FastLED.show();

}


// ***************************************       MAIN LOOP       ***********************************************

void loop() {

  // **********     RFID-leser     **********

  // Reset the loop if no new card present on the sensor/reader. This saves the entire process when idle.
  if (!rfid.PICC_IsNewCardPresent()) {
    // Serial.print("No card");
    delay(100);       // et lite delay før vi sjekker igjen
    return;
  }

  // Verify if the NUID has been read
  if (!rfid.PICC_ReadCardSerial())
    return;

  MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);

  // Check is the PICC of Classic MIFARE type
  if (piccType != MFRC522::PICC_TYPE_MIFARE_MINI && piccType != MFRC522::PICC_TYPE_MIFARE_1K && piccType != MFRC522::PICC_TYPE_MIFARE_4K) {
    Serial.println(F("Your tag is not of type MIFARE Classic."));
    leds[2] = CRGB::Red;
    FastLED.show();
    delay(200);
    leds[2] = CRGB::Black;
    FastLED.show();
    return;
  }

  if ((timers[timLastTagRead].elapsedTime() > minimum_split * 1000) || (rfid.uid.uidByte[0] != nuidPICC.data[0] || rfid.uid.uidByte[1] != nuidPICC.data[1] || rfid.uid.uidByte[2] != nuidPICC.data[2] || rfid.uid.uidByte[3] != nuidPICC.data[3])) {
    Serial.println(F("A new card has been detected."));
    Serial.println("timLastTagRead.elapsedTime: " + String(timers[timLastTagRead].elapsedTime()));

    // Store NUID into nuidPICC array
    for (byte i = 0; i < 4; i++) {
      nuidPICC.data[i] = rfid.uid.uidByte[i];
    }
    // nuidPICC.timestamp = timers[timOn].elapsedTime();
    nuidPICC.timestamp = millis();

    // Lagre tag i ringbuffer
    Serial.print("loop ber om xMutex...");
    if (xSemaphoreTake (xMutex, portMAX_DELAY)) {
      Serial.print("loop tok xMutex...");
      ringBuffer.add(nuidPICC);
      ringBuffer.printAll();
      Serial.println("loop gir tilbake xMutex");
      xSemaphoreGive (xMutex);  // release the mutex
      Serial.println("Lagt til ny tag i ringBuffer");
      leds[0] = CRGB::Green;
      leds[1] = CRGB::Green;
      leds[2] = CRGB::Green;
      FastLED.show();
      delay(350);
      leds[0] = CRGB::Black;
      leds[1] = CRGB::Black;
      leds[2] = CRGB::Black;
      FastLED.show();
    }

    timers[timLastTagRead].start();

  } else {
    Serial.println(F("Card read previously."));
      leds[0] = CRGB::Red;
      leds[2] = CRGB::Yellow;
      FastLED.show();
      delay(350);
      leds[0] = CRGB::Black;
      leds[2] = CRGB::Black;
      FastLED.show();
  }

  // Halt PICC
  rfid.PICC_HaltA();

  // Stop encryption on PCD
  rfid.PCD_StopCrypto1();

}