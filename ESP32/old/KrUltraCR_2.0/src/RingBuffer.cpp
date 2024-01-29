#include "../RingBuffer.h"

// Definisjon av ringbufferet
RFIDTag ringBuffer[bufferSize];

// Variabel for å holde rede på antall registreringer i ringbufferet
int numRegistrations = 0;

// Peker for å holde oversikt over neste ledige plass i bufferet
int nextIndex = 0;

// Funksjon for å registrere en RFID-tag og legge den i ringbufferet
void registerRFIDTag(const RFIDTag& tagData) {
    // Kopier RFID-dataene til ringbufferet på riktig indeks
    memcpy(ringBuffer[nextIndex].data, &tagData, sizeof(byte) * 4);

    // Inkrementer neste ledige indeks med wrap-around
    nextIndex = (nextIndex + 1) % bufferSize;

    // Øk antall registreringer, men ikke over bufferSize
    if (numRegistrations < bufferSize) {
        numRegistrations++;
    }
}

// Funksjon for å fjerne den eldste RFID-taggen fra ringbufferet (FIFO-prinsippet)
void removeOldestTag() {
    // Sjekk om det er noen registreringer i bufferet
    if (numRegistrations > 0) {
        // Oppdater antall registreringer og juster `nextIndex` til å peke på den eldste taggen
        numRegistrations--;
        nextIndex = (nextIndex + bufferSize - 1) % bufferSize;
    }
}

// Funksjon for å hente den eldste RFID-taggen fra ringbufferet
const RFIDTag& getOldestTag() {
    // Sjekk om det er noen registreringer i bufferet
    if (numRegistrations > 0) {
        // Beregn indeksen til den eldste taggen
        int oldestIndex = (nextIndex + bufferSize - numRegistrations) % bufferSize;

        // Returner referansen til den eldste taggen
        return ringBuffer[oldestIndex];
    } else {
        // Hvis det ikke er noen registreringer, returner en null-referanse
        return ringBuffer[0];
    }
}

// Funksjon for å skrive ut innholdet i ringbufferet
void printRingBuffer() {
    Serial.println("---- Ringbuffer ----");
    for (int i = 0; i < numRegistrations; i++) {
        int index = (nextIndex + bufferSize - numRegistrations + i) % bufferSize;
        Serial.print("Index ");
        Serial.print(index);
        Serial.print(": ");
        for (int j = 0; j < 4; j++) {
            Serial.print(ringBuffer[index].data[j], HEX);
            Serial.print(" ");
        }
        Serial.println();
    }
    Serial.println("--------------------");
}

