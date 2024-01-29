#ifndef RingBuffer_h
#define RingBuffer_h

#include <Arduino.h>

// Definer størrelsen på ringbufferet
const int bufferSize = 10;

// Definer strukturen for en RFID-tag

struct RFIDTag {
    byte data[4];
};

// Opprett ringbufferet
extern RFIDTag ringBuffer[bufferSize];

// Variabel for å holde rede på antall registreringer i ringbufferet
extern int numRegistrations;

// Peker for å holde oversikt over neste ledige plass i bufferet
extern int nextIndex;

// Funksjon for å registrere en RFID-tag og legge den i ringbufferet
void registerRFIDTag(const RFIDTag& tagData);

// Funksjon for å fjerne den eldste RFID-taggen fra ringbufferet (FIFO-prinsippet)
void removeOldestTag();

// Funksjon for å hente den eldste RFID-taggen fra ringbufferet
const RFIDTag& getOldestTag();

// Funksjon for å skrive ut innholdet i ringbufferet
void printRingBuffer();

#endif
