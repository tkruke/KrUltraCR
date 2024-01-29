/*******************************************************************************************
 * KrUltraCR 2.0.002
 * 
 * Checkpoint Registration system
 * By Torgeir Kruke (C) 2023
 *******************************************************************************************/


// **************************************    INIT     *************************************

// Kompilatordirektiver og variabeldeklarasjoner
#include <Preferences.h>
#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <MySQL_Generic.h>
#include "Credentials.h"
#include "RingBuffer.h"
#include "Timer.h"

#define MY_DEBUG_PORT Serial
String debugMessage = "";
#define cpuFrequency 80
Preferences preferences;      // Brukes for å finne antall boot-sekvenser som er kjørt
uint64_t rfid_reader_chip_id = ESP.getEfuseMac(); // Hent chip-ID

// For kommunikasjon med RC522 og lesing av rfid-brikker
#define SS_PIN 21
#define RST_PIN 22
MFRC522 rfid(SS_PIN, RST_PIN);  // Instance of the class
MFRC522::MIFARE_Key key;
RingBuffer ringBuffer;
RingBuffer::RFIDTag nuidPICC = RingBuffer::createRFIDTag();  // Variable that will store new NUID before adding it to the ring buffer
int minimum_split = 10000;   //     minimum tid mellom lesing av samme rfid-tag i millisekunder (10000 = 10 sekunder)
bool default_minimum_split = true;  // flagg som varsler at minimum_split ikke er lest fra db ennå

// For MySQL-kommunikasjon
#define _MYSQL_LOGLEVEL_ 1    // Debug Level from 0 to 4
String test_table = "test";
String test_column = "testcol";
String test_value = "Hello! Testing, testing... 1-2-3-4";  // til testing
MySQL_Connection conn((Client*)&client);
MySQL_Query query_mem = MySQL_Query(&conn);


// Timere, bl.a. for å oppnå asynkrone prosesser for wifi- og database-oppkoblinger
const int MAX_TIMERS = 5; // Antall timerobjekter - utvides etter behov
#define timOn 0   // timer for å timestampe rfid-registreringer
#define timWifiConn 1
const unsigned long maxWifiConnTime = 60000;      // millisekunder
#define timAwaitWifiRetry 2
const unsigned long awaitWifiRetryTime = 300000;   // millisekunder
#define timTick 3
const unsigned long tickTime = 1000;   // millisekunder
#define timLastTagRead 4
Timer timers[MAX_TIMERS]; // Array for timerobjekter

// *************************************    FUNCTIONS      *******************************************************

/**
 * Function used to run SQL command on database
 **/
bool runSQL(const String sqlStatement) {
  // Initiate the query class instance

  if (conn.connected()) {
    // MYSQL_DISPLAY(sqlStatement);

    // Execute the query
    // KH, check if valid before fetching
    if (!query_mem.execute(sqlStatement.c_str()))  // Utfører SQL-setningen
    {
      MYSQL_DISPLAY("Insert error");
      return false;
    } else {
      MYSQL_DISPLAY("Data Inserted.");
      return true;
    }
  } else {
    MYSQL_DISPLAY("Disconnected from Server. Can't insert.");
    return false;
  }
}

/**
 * Helper routine to dump a byte array as dec values to MY_DEBUG_PORT.
 */
// void printDec(byte* buffer, byte bufferSize) {
//   for (byte i = 0; i < bufferSize; i++) {
//     MY_DEBUG_PORT.print(buffer[i] < 0x10 ? " 0" : " ");
//     MY_DEBUG_PORT.print(buffer[i], DEC);
//   }
// }

/**
 * Funksjon som oppdaterer databasen med rfid-registreringer fra ringbufferet
 */
bool dbUpdate() {
  if (!WiFi.isConnected()) {
    MY_DEBUG_PORT.println(F("No wifi - skip dbUpdate"));
  return false; 
  }

  String sqlStatement;    // bruk sqlStatement.c_str() som parameter når sql-setningen skal eksekveres (.execute)

  MY_DEBUG_PORT.print(F("Kobler opp mot database..."));

  // conn.connect(server, server_port, user, password)
  // MY_DEBUG_PORT.println("conn.connectNonBlocking(" + String(db_server_name) + ", " + String(db_server_port) + ", " + String(db_user) + ", " + String(db_password) + ")");
  if (conn.connected() || (conn.connectNonBlocking(server, db_server_port, db_user, db_password) != RESULT_FAIL)) {
    MY_DEBUG_PORT.println(F("OK"));
    // delay(500);  // legg til forsinkelse hvis testing viser det nødvendig
    String tagStr = "0-0-0-0";
    RingBuffer::RFIDTag oldestTag = ringBuffer.getOldest();
    String segments[4];
    // Konverter hvert byte til en streng og lagre den i segments-arrayet
    for (int i = 0; i < 4; i++) {
        segments[i] = String(oldestTag.data[i]);
    }
    tagStr = segments[0] + "-" + segments[1] + "-" + segments[2] + "-" + segments[3];
    int reg_delay_ms = millis() - oldestTag.timestamp;
    String sqlStatement = String("INSERT INTO ") + database + "." + registration_table
                          + " (rfid_reader_chip_id, rfid_tag_uid, reg_delay_ms) VALUES ("
                          + String(rfid_reader_chip_id) + ", '" + tagStr + "', " + reg_delay_ms + ")";
    if (runSQL(sqlStatement)) {
      if (ringBuffer.count() == 0) {
        conn.close();   // close the connection only if no more registrations are in the queue
      }
      return true;
    } else {
      conn.close();
      return false;
    }
  } else {
    MYSQL_DISPLAY("\nConnect failed. Trying again on next iteration.");
    conn.close();
    return false;
  }
}

bool wifiConnect() {
  WiFi.begin(default_wifi_ssid, default_wifi_password);
  // Auto reconnect is set true as default
  // To set auto connect off, use the following function
  //    WiFi.setAutoReconnect(false);

  // Will try for about 10 seconds (20x 500ms)
  int tryDelay = 500;
  int numberOfTries = 20;

  // Wait for the WiFi event
  while (true) {

    switch (WiFi.status()) {
      case WL_NO_SSID_AVAIL:
        MY_DEBUG_PORT.println("[WiFi] SSID not found");
        break;
      case WL_CONNECT_FAILED:
        MY_DEBUG_PORT.print("[WiFi] Failed - WiFi not connected! Reason: ");
        return false;
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
        return true;
        break;
      default:
        MY_DEBUG_PORT.print("[WiFi] WiFi Status: ");
        MY_DEBUG_PORT.println(WiFi.status());
        break;
    }
    delay(tryDelay);

    if (numberOfTries <= 0) {
      MY_DEBUG_PORT.print("[WiFi] Failed to connect to WiFi!");
      // This function will disconnect and turn off the WiFi (NVS WiFi data is kept)
      if (WiFi.disconnect(true, false)) {
        MY_DEBUG_PORT.println(F("[WiFi] Disconnected from WiFi!"));
      }
      return false;
    } else {
      numberOfTries--;
    }
  }
}

bool getMinimumSplit() {
  // MY_DEBUG_PORT.println(F("Starter getMinimumSplit"));
  
  if (!WiFi.isConnected()) {
    MY_DEBUG_PORT.println(F("No wifi - skip database connection"));
  return false; 
  }

  // Initialize variables for the function
  row_values *row = NULL;
  long minimum_split = 0;
  String sqlStatement = "";    // bruk sqlStatement.c_str() som parameter når sql-setningen skal eksekveres (.execute)

  if (conn.connected() || (conn.connectNonBlocking(server, db_server_port, db_user, db_password) != RESULT_FAIL)) {

    // Initiate the query class instance
    MySQL_Query _query_mem = MySQL_Query(&conn);

    // Build the SQL statement
    sqlStatement = String("SELECT checkpoint.minimum_split AS minimum_split FROM " + database + ".checkpoint JOIN " +
                            database + ".rfid_reader ON rfid_reader.checkpoint_id = checkpoint.id WHERE rfid_reader.chip_id = ") + 
                            String(rfid_reader_chip_id);

    // Display and Execute the query
    MYSQL_DISPLAY(sqlStatement.c_str());
    if (!_query_mem.execute(sqlStatement.c_str()))  // Execute the SQL statement
    {
      MYSQL_DISPLAY("DB Query error");
      _query_mem.close();
      conn.close();
      return false;
    } 

    _query_mem.get_columns();             // Fetch the columns (required) even if we don't use them.
    row = _query_mem.get_next_row();      // Read the row (we are only expecting one)
    int minimum_split_in_seconds = 10;    // default
    while (row != NULL) 
    { 
        minimum_split_in_seconds = atoi(row->values[0]);
        row = _query_mem.get_next_row(); 
    }    
    minimum_split = minimum_split_in_seconds * 1000;             // konverterer fra sekunder til mikrosekunder
    MYSQL_DISPLAY1("Minimum split value: ", minimum_split);

    // Rydd og avslutt med suksess
    _query_mem.close();
    conn.close();
    default_minimum_split = false;
    return true;
  } else {
    MYSQL_DISPLAY("DB Connect failed");
    conn.close();
    return false;
  }
}

// *****************************************    SETUP     ***********************************************************
void setup() {

  MY_DEBUG_PORT.begin(19200);
  while (!MY_DEBUG_PORT && millis() < 5000);  // wait for MY_DEBUG_PORT to connect

  setCpuFrequencyMhz(cpuFrequency);     // juster ned cpu-frekvensen for å redusere strømforbruket

  timers[timOn].start();
  timers[timWifiConn].setMaxTime(maxWifiConnTime);    // maxWifiConnTime settes i antall millisekunder
  timers[timTick].setMaxTime(tickTime);            // tickTime settes i antall millisekunder

  // Les antall ganger oppstart har skjedd - kan lagres sammen med tid for å ta hensyn til at tiden blir nullstilt hver gang det bootes
  preferences.begin("KrUltraCR", false);   // Open Preferences with KrUltraCR namespace (max 15 char).
  unsigned int startCounter = preferences.getUInt("KrUltraCRcount", 0);
  Serial.printf("Previous counter value: %u\n", startCounter);
  startCounter++;
  Serial.printf("Current counter value: %u\n", startCounter);
  preferences.putUInt("KrUltraCRcount", startCounter);    // Store the counter to the Preferences
  startCounter = preferences.getUInt("KrUltraCRcount", 0);
  Serial.printf("Updated counter value: %u\n", startCounter);
  preferences.end();                          // Close the Preferences

  // Koble opp mot databasen og hent parametre
  if (wifiConnect()) {
    MY_DEBUG_PORT.println(F("[WiFi] Connected to WiFi!"));
    MY_DEBUG_PORT.println(F("Minimum split value default = " + minimum_split));
    if (!getMinimumSplit()) {
      minimum_split = default_minimum_split;
    };
    // This function will disconnect and turn off the WiFi (NVS WiFi data is kept)
    if (WiFi.disconnect(true, false)) {
      MY_DEBUG_PORT.println(F("[WiFi] Disconnected from WiFi!"));
    }
  } else {
    minimum_split = default_minimum_split;
  }

  // Start kommunikasjon med RC522
  SPI.begin();      // Init SPI bus
  rfid.PCD_Init();  // Init MFRC522
  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }
  MY_DEBUG_PORT.println(F("This code scan the MIFARE Classsic NUID."));
}


// ***************************************       MAIN LOOP       ***********************************************

void loop() {

if ((ringBuffer.count() > 0) && !timers[timAwaitWifiRetry].isActive()) {       // Elementer i kø som skal overføres til databasen

// **********     Oppkobling og oppdatering av database     **********

  if (WiFi.status() != WL_CONNECTED) {             // Opprett wifi-forbindelse
    if (!timers[timWifiConn].isActive()) {   
      MY_DEBUG_PORT.print(F("Start wifi"));
      WiFi.begin(default_wifi_ssid, default_wifi_password);
      timers[timWifiConn].start();
      timers[timTick].start();
    }
  }
  else {    // WiFi-forbindelse i orden - kjør databaseoppdatering
    timers[timTick].setIdle();
    MY_DEBUG_PORT.println("OK");    
    if (default_minimum_split) {
      getMinimumSplit();
    }
    if (dbUpdate()) {
      ringBuffer.removeOldest();  // for testing - simulerer at en rfid-registrering ble skrevet til databasen og kan fjernes fra ringbufferet
      MY_DEBUG_PORT.println("One RFIDTag removed from ring buffer!");
    }
    debugMessage = "[DB] db update(s) for " + String(ringBuffer.count()) + " entries remaining";
    MY_DEBUG_PORT.println(F(debugMessage.c_str()));
    if (ringBuffer.count() == 0) {
      MY_DEBUG_PORT.println(F("[WiFi] Disconnecting from WiFi"));
      timers[timWifiConn].setIdle();
      // This function will disconnect and turn off the WiFi (NVS WiFi data is kept)
      if (WiFi.disconnect(true, false)) {
        MY_DEBUG_PORT.println(F("[WiFi] Disconnected from WiFi!"));
      }
    }
  }
}

// **********     Timer-håndtering     **********

  // debugMessage = "[Timer] timWifiConn: " + (timers[timAwaitWifiRetry].isActive() ? String("active") : String("inactive")) + " / elapsed " + String(timers[timAwaitWifiRetry].elapsedTime()) + "ms";
  // MY_DEBUG_PORT.println(F(debugMessage.c_str()));

if ((timers[timWifiConn].isActive()) && (timers[timWifiConn].elapsedTime() > timers[timWifiConn].getMaxTime())) {
  MY_DEBUG_PORT.print(F("Debug 4... "));
  timers[timAwaitWifiRetry].start();
  timers[timWifiConn].setIdle();
  timers[timTick].setIdle();
  debugMessage = "\nNo wifi connection achieved within time limit of " + String(maxWifiConnTime / 1000) + " s\nRetry in max " + String(awaitWifiRetryTime / 1000) + " s";
  MY_DEBUG_PORT.println(F(debugMessage.c_str()));
}

if (timers[timTick].isActive()) {
  if (timers[timTick].elapsedTime() > timers[timTick].getMaxTime()) {
    MY_DEBUG_PORT.print(F("."));
    timers[timTick].start();
  }
}

if (timers[timAwaitWifiRetry].isActive() && (timers[timAwaitWifiRetry].elapsedTime() > awaitWifiRetryTime)) {
  MY_DEBUG_PORT.print(F("Debug 6... "));
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

// MY_DEBUG_PORT.print(F("PICC type: "));
MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
// MY_DEBUG_PORT.println(rfid.PICC_GetTypeName(piccType));

// Check is the PICC of Classic MIFARE type
if (piccType != MFRC522::PICC_TYPE_MIFARE_MINI && piccType != MFRC522::PICC_TYPE_MIFARE_1K && piccType != MFRC522::PICC_TYPE_MIFARE_4K) {
  MY_DEBUG_PORT.println(F("Your tag is not of type MIFARE Classic."));
  return;
}

if ((timers[timLastTagRead].elapsedTime() > minimum_split) || (rfid.uid.uidByte[0] != nuidPICC.data[0] || rfid.uid.uidByte[1] != nuidPICC.data[1] || rfid.uid.uidByte[2] != nuidPICC.data[2] || rfid.uid.uidByte[3] != nuidPICC.data[3])) {
  MY_DEBUG_PORT.println(F("A new card has been detected."));
  MY_DEBUG_PORT.println("timLastTagRead.elapsedTime: " + timers[timLastTagRead].elapsedTime());

  // Store NUID into nuidPICC array
  for (byte i = 0; i < 4; i++) {
    nuidPICC.data[i] = rfid.uid.uidByte[i];
  }
  nuidPICC.timestamp = timers[timOn].elapsedTime();

  // Lagre tag i ringbuffer
  ringBuffer.add(nuidPICC);
  ringBuffer.printAll();

} else MY_DEBUG_PORT.println(F("Card read previously."));

timers[timLastTagRead].start();

// Halt PICC
rfid.PICC_HaltA();

// Stop encryption on PCD
rfid.PCD_StopCrypto1();

}