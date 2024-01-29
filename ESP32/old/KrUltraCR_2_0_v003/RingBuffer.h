#ifndef RingBuffer_h
#define RingBuffer_h

#include <Arduino.h>

class RingBuffer {
private:
    static const int _capacity = 1000; // Definer størrelsen på ringbufferet

    struct Tag {
        byte data[4];
        unsigned long timestamp;
    };

    Tag _buffer[_capacity];    // Opprett ringbufferet
    int _size = 0;      // Variabel for å holde rede på antall registreringer i ringbufferet
    int _next = 0;      // Peker for å holde oversikt over neste ledige plass i bufferet

public:
    // Funksjon for å opprette en variabel av type RFIDTag
    using RFIDTag = Tag;
    static RFIDTag createRFIDTag();

    // Funksjon for å registrere en RFID-tag og legge den i ringbufferet
    void add(const RFIDTag& tagData);

    // Funksjon for å hente den eldste RFID-taggen fra ringbufferet
    const RFIDTag& getOldest() const;

    // Funksjon for å fjerne den eldste RFID-taggen fra ringbufferet (FIFO-prinsippet)
    void removeOldest();

    // Funksjon for å skrive ut innholdet i ringbufferet
    void printAll() const;

    // Funksjon for å returnere antall elementer i ringbufferet
    const int count() const;
};

#endif

