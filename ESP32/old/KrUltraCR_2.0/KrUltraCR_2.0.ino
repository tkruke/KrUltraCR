/*******************************************************************************************
 * KrUltraCR v2
 * 
 * Checkpoint Registration system
 * By Torgeir Kruke (C) 2023
 *******************************************************************************************/


// **************************************    INIT     *************************************

// Kompilatordirektiver og variabeldeklarasjoner
#include <WiFi.h>
#include <SPI.h>
#include <MFRC522.h>
#include <MySQL_Generic.h>
#include "Credentials.h"
#include "RingBuffer.h"
#include <Preferences.h>

// For kommunikasjon med RC522 og lesing av rfid-brikker
#define SS_PIN 21
#define RST_PIN 22
MFRC522 rfid(SS_PIN, RST_PIN);  // Instance of the class
MFRC522::MIFARE_Key key;
RFIDTag nuidPICC = {0};  // Init array that will store new NUID

// For MySQL-kommunikasjon
#define MY_DEBUG_PORT Serial
String message = "";
#define _MYSQL_LOGLEVEL_ 1    // Debug Level from 0 to 4
// char test_table[] = "test";                              // til testing
// char test_column[] = "testcol";                          // til testing
String test_table = "test";
String test_column = "testcol";
String test_value = "Hello! Testing, testing... 1-2-3";  // til testing
MySQL_Connection conn((Client*)&client);
MySQL_Query* query_mem;

String sqlStatement;    // bruk sqlStatement.c_str() som parameter når sql-setningen skal eksekveres (.execute)
// String mySqlString = "SELECT * FROM test";
Preferences preferences;      // Brukes for å finne antall boot-sekvenser som er kjørt

#define cpuFrequency 80
unsigned long long cyclesPerMicrosecond = cpuFrequency * 1000000ULL;

struct Timer {
  bool active = false; 
  unsigned long long startTime = 0;
  unsigned long long maxTime = 0;

  void setIdle() {
    startTime = 0;
    active = false;
  }

  void start() {
    startTime = ESP.getCycleCount();
    active = true;
  }

  unsigned long long elapsedTime() {
    unsigned long long currentTime = ESP.getCycleCount();
    unsigned long long elapsedTimeMicros = (currentTime - startTime) / cyclesPerMicrosecond;
    return elapsedTimeMicros;
  }
};

const int MAX_TIMERS = 4; // Antall timerobjekter - utvides etter behov
#define timOn 0
#define timWifiConn 1
const unsigned long long maxWifiConnTime = 60ULL;      // settes i sekunder - juster basert på erfaring
#define timAwaitWifiRetry 2
const unsigned long long awaitWifiRetryTime = 300ULL;   // settes i sekunder
#define timTick 3
const unsigned long long maxTickTime = 1ULL;   // settes i sekunder
Timer timers[MAX_TIMERS]; // Array for timerobjekter

// *************************************    FUNCTIONS      *******************************************************

/** Se funksjoner skilt ut i egne moduler i underkatalog ./src
 * RingBuffer.ccp - funksjoner for bruk av et ringbuffer for mellomlagring av registrerte rfid-tagger
 **/

/**
 * Funskjon for å koble til wifi
 **/
 void connectWiFi(String wifi_ssid, String wifi_password, int tryDelay, int numberOfTries) {
  MY_DEBUG_PORT.println();
  MY_DEBUG_PORT.print("[WiFi] Connecting to ");
  MY_DEBUG_PORT.println(wifi_ssid);

  WiFi.begin(wifi_ssid, wifi_password);

  // // Will try for about 10 seconds (20x 500ms)
  // int tryDelay = 200;       // 500
  // int numberOfTries = 5;    // 20 - men dette sperrer for lesing av nye kort, og hvis det tar flere sekunder så er det ikke gunstig

  // Wait for the WiFi event
  while (true) {

    switch (WiFi.status()) {
      case WL_NO_SSID_AVAIL:
        MY_DEBUG_PORT.println("[WiFi] SSID not found");
        break;
      case WL_CONNECT_FAILED:
        MY_DEBUG_PORT.print("[WiFi] Failed - WiFi not connected! Reason: ");
        return;
        break;
      case WL_CONNECTION_LOST:
        MY_DEBUG_PORT.println("[WiFi] Connection was lost");
        break;
      case WL_SCAN_COMPLETED:
        MY_DEBUG_PORT.println("[WiFi] Scan is completed");
        break;
      case WL_DISCONNECTED:
        MY_DEBUG_PORT.println("[WiFi] WiFi is disconnected");
        break;
      case WL_CONNECTED:
        MY_DEBUG_PORT.println("[WiFi] WiFi is connected!");
        MY_DEBUG_PORT.print("[WiFi] IP address: ");
        MY_DEBUG_PORT.println(WiFi.localIP());
        return;
        break;
      default:
        MY_DEBUG_PORT.print("[WiFi] WiFi Status: ");
        MY_DEBUG_PORT.println(WiFi.status());
        break;
    }
    delay(tryDelay);

    if (numberOfTries <= 0) {
      MY_DEBUG_PORT.print("[WiFi] Failed to connect to WiFi!");
      // Use disconnect function to force stop trying to connect
      WiFi.disconnect();
      return;
    } else {
      numberOfTries--;
    }
  }
 }

/**
 * Hjelpefunksjon for å bygge opp sql-setning
 **/
// void buildSqlInsertStatement(char* buffer, int bufferSize, const char* table, String& columns, String& values) {
//   snprintf(buffer, bufferSize, "INSERT INTO %s.%s (%s) VALUES ('%s')", database, table, columns.c_str(), values.c_str());
// }

/**
 * Function used to run SQL command on database
 **/
void runSQL(const char* sqlStatement) {
  // Initiate the query class instance
  MySQL_Query query_mem = MySQL_Query(&conn);

  if (conn.connected()) {
    MYSQL_DISPLAY(sqlStatement);

    // Execute the query
    // KH, check if valid before fetching
    if (!query_mem.execute(sqlStatement))  // Utfører SQL-setningen
    {
      MYSQL_DISPLAY("Insert error");
    } else {
      MYSQL_DISPLAY("Data Inserted.");
    }
  } else {
    MYSQL_DISPLAY("Disconnected from Server. Can't insert.");
  }
}

/**
 * Helper routine to dump a byte array as hex values to MY_DEBUG_PORT. 
 */
// void printHex(byte* buffer, byte bufferSize) {
//   for (byte i = 0; i < bufferSize; i++) {
//     MY_DEBUG_PORT.print(buffer[i] < 0x10 ? " 0" : " ");
//     MY_DEBUG_PORT.print(buffer[i], HEX);
//   }
// }

/**
 * Helper routine to dump a byte array as dec values to MY_DEBUG_PORT.
 */
void printDec(byte* buffer, byte bufferSize) {
  for (byte i = 0; i < bufferSize; i++) {
    MY_DEBUG_PORT.print(buffer[i] < 0x10 ? " 0" : " ");
    MY_DEBUG_PORT.print(buffer[i], DEC);
  }
}

void dbUpdate() {
  MYSQL_DISPLAY("Connecting...");
  MYSQL_DISPLAY1("\nStarting Basic_Insert_ESP on", ARDUINO_BOARD);
  MYSQL_DISPLAY(MYSQL_MARIADB_GENERIC_VERSION);

  // conn.connect(server, server_port, user, password)
  if (conn.connectNonBlocking(db_server_name, db_server_port, db_user, db_password) != RESULT_FAIL) {
    delay(500);
    // buildSqlInsertStatement(sqlStatement, sizeof(sqlStatement), test_table, test_column, test_value.c_str());
    sqlStatement = "INSERT INTO " + database +"." + test_table + " (" + test_column + ") VALUES ('" + test_value + "')";
    runSQL(sqlStatement.c_str());
    conn.close();  // close the connection
  } else {
    MYSQL_DISPLAY("\nConnect failed. Trying again on next iteration.");
  }

}


// *****************************************    SETUP     ***********************************************************
void setup() {

  MY_DEBUG_PORT.begin(9600);
  while (!MY_DEBUG_PORT && millis() < 5000);  // wait for MY_DEBUG_PORT to connect

  setCpuFrequencyMhz(cpuFrequency);     // juster ned cpu-frekvensen for å spare strøm

  timers[timOn].start();
  timers[timWifiConn].maxTime = maxWifiConnTime * cyclesPerMicrosecond * 1000000ULL;    // maxWifiConnTime settes i antall sekunder
  timers[timTick].maxTime = maxTickTime * cyclesPerMicrosecond * 1000000ULL;            // maxTickTime settes i antall sekunder

  // Les antall ganger oppstart har skjedd - kan lagres sammen med tid for å ta hensyn til at tiden blir nullstilt hver gang det bootes
  preferences.begin("KrUltraCR", false);   // Open Preferences with KrUltraCR2.0 namespace (max 15 char).
  unsigned int startCounter = preferences.getUInt("KrUltraCRcounter", 0);
  startCounter++;
  Serial.printf("Current counter value: %u\n", startCounter);
  preferences.putUInt("KrUltraCRcounter", startCounter);    // Store the counter to the Preferences
  preferences.end();                          // Close the Preferences

  // Start kommunikasjon med RC522
  SPI.begin();      // Init SPI bus
  rfid.PCD_Init();  // Init MFRC522
  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }
  MY_DEBUG_PORT.println(F("This code scan the MIFARE Classsic NUID."));
  MY_DEBUG_PORT.print(F("Using the following key:"));
  printDec(key.keyByte, MFRC522::MF_KEY_SIZE);

  // Connect to WiFi network 
  // WiFi.setAutoReconnect(false);                     // default = true 
  // connectWiFi(default_wifi_ssid, default_wifi_password, 500, 20);   // default ssid og passord defineres i Credentials.h. 500 ms pause mellom hvert forsøk, og max 20 forsøk (10 sekunder)

}


// ***************************************       MAIN LOOP       ***********************************************

void loop() {

if (numRegistrations > 0) {       // Forsøk wifi-oppkobling og 

  if (!WiFi.status == WL_CONNECTED && !timers[timAwaitWifiRetry].active) {
    MY_DEBUG_PORT.println(F("Debug 001"));
    if (!timers[timWifiConn].active) {    // Begynn forsøk på å opprette wifi-forbindelse
      MY_DEBUG_PORT.println(F("Forsøker å starte wifi"));
      WiFi.begin(default_wifi_ssid, default_wifi_password);
      timers[timWifiConn].start();
      timers[timTick].start();
    }
    else {  // Forsøk på å opprette wifi-forbindelse pågår, sjekk status
      switch (WiFi.status()) {
        case WL_NO_SSID_AVAIL:
          MY_DEBUG_PORT.println(F("[WiFi] SSID not found"));
          timers[timWifiConn].setIdle();
          timers[timTick].setIdle();
          timers[timAwaitWifiRetry].start();
          break;
        case WL_CONNECT_FAILED:
          MY_DEBUG_PORT.println(F("[WiFi] Failed - WiFi not connected!"));
          timers[timWifiConn].setIdle();
          timers[timTick].setIdle();
          timers[timAwaitWifiRetry].start();
          break;
        case WL_CONNECTION_LOST:
          MY_DEBUG_PORT.println(F("[WiFi] Connection was lost"));
          timers[timWifiConn].setIdle();
          timers[timTick].setIdle();
          timers[timAwaitWifiRetry].start();
          break;
        case WL_SCAN_COMPLETED:
          MY_DEBUG_PORT.println(F("[WiFi] Scan is completed"));
          timers[timWifiConn].setIdle();
          timers[timTick].setIdle();
          timers[timAwaitWifiRetry].start();
          break;
        case WL_DISCONNECTED:
          MY_DEBUG_PORT.println(F("[WiFi] WiFi is disconnected"));
          timers[timWifiConn].setIdle();
          timers[timTick].setIdle();
          timers[timAwaitWifiRetry].start();
          break;
        case WL_CONNECTED:
          MY_DEBUG_PORT.println(F("[WiFi] WiFi is connected!"));
          MY_DEBUG_PORT.print(F("[WiFi] IP address: "));
          MY_DEBUG_PORT.println(WiFi.localIP());
          break;
        default:
          // do nothing - attempt to establish wifi connection continues
          break;
      }
    }
  }
  else {    // WiFi-forbindelse i orden - kjør databaseoppdatering
    MY_DEBUG_PORT.println(F("Debug 002"));
    message = "[DB] Preparing db update(s) for " + String(numRegistrations) + " entries";
    MY_DEBUG_PORT.println(F(message.c_str()));
    // dbUpdate();
    numRegistrations--;  // for testing - simulerer at en rfid-registrering ble skrevet til databasen
    // Disconnect from WiFi - NB: Bare hvis dbUpdate var ok!
    if (numRegistrations == 0) {
      MY_DEBUG_PORT.println(F("[WiFi] Disconnecting from WiFi!"));
      // This function will disconnect and turn off the WiFi (NVS WiFi data is kept)
      if (WiFi.disconnect(true, false)) {
        MY_DEBUG_PORT.println(F("[WiFi] Disconnected from WiFi!"));
      }
    }
  }
}

// **********     Timer-håndtering     **********

if ((timers[timWifiConn].active) && (timers[timWifiConn].elapsedTime() > timers[timWifiConn].maxTime)) {
  timers[timAwaitWifiRetry].start();
  timers[timWifiConn].setIdle();
  timers[timTick].setIdle();
  message = "\nNo wifi connection achieved within time limit of " + String(maxWifiConnTime) + "\nRetry in max " + String(awaitWifiRetryTime).c_str() + " seconds";
  MY_DEBUG_PORT.println(F(message.c_str()));
}

if (timers[timTick].active) {
  if (timers[timTick].elapsedTime() > timers[timTick].maxTime) {
    MY_DEBUG_PORT.print(F("."));
    timers[timTick].start();
  }
}

if (timers[timAwaitWifiRetry].active && timers[timAwaitWifiRetry].elapsedTime() > awaitWifiRetryTime) {
  timers[timAwaitWifiRetry].setIdle();
  MY_DEBUG_PORT.println(F("Ready for wifi connection retry"));
}

// **********     RFID-leser     **********

// Reset the loop if no new card present on the sensor/reader. This saves the entire process when idle.
if (!rfid.PICC_IsNewCardPresent())
  return;

// Verify if the NUID has been read
if (!rfid.PICC_ReadCardSerial())
  return;

MY_DEBUG_PORT.print(F("PICC type: "));
MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
MY_DEBUG_PORT.println(rfid.PICC_GetTypeName(piccType));

// Check is the PICC of Classic MIFARE type
if (piccType != MFRC522::PICC_TYPE_MIFARE_MINI && piccType != MFRC522::PICC_TYPE_MIFARE_1K && piccType != MFRC522::PICC_TYPE_MIFARE_4K) {
  MY_DEBUG_PORT.println(F("Your tag is not of type MIFARE Classic."));
  return;
}

if (rfid.uid.uidByte[0] != nuidPICC.data[0] || rfid.uid.uidByte[1] != nuidPICC.data[1] || rfid.uid.uidByte[2] != nuidPICC.data[2] || rfid.uid.uidByte[3] != nuidPICC.data[3]) {
  MY_DEBUG_PORT.println(F("A new card has been detected."));

  // Store NUID into nuidPICC array
  for (byte i = 0; i < 4; i++) {
    nuidPICC.data[i] = rfid.uid.uidByte[i];
  }

  MY_DEBUG_PORT.println(F("The NUID tag is:"));
  printDec(rfid.uid.uidByte, rfid.uid.size);
  MY_DEBUG_PORT.println();

  // Lagre tag i ringbuffer
  registerRFIDTag(nuidPICC);

  // Connect to WiFi
  // *** TBD ***

  // Store to db
  // *** TBD ***

} else MY_DEBUG_PORT.println(F("Card read previously."));

// Halt PICC
rfid.PICC_HaltA();

// Stop encryption on PCD
rfid.PCD_StopCrypto1();



}