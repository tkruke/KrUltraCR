#include "../RingBuffer.h"

// Funksjon for å opprette en variabel av type RFIDTag
RingBuffer::RFIDTag RingBuffer::createRFIDTag() {
    RFIDTag newTag = {0};  // or however you want to initialize it
    return newTag;
}

// Funksjon for å registrere en RFID-tag og legge den i ringbufferet
void RingBuffer::add(const RFIDTag& tagData) {
    // Kopier RFID-dataene til ringbufferet på riktig indeks
    memcpy(&_buffer[_next], &tagData, sizeof(Tag));
    // if (&tagData.timestamp == 0) {
    //     _buffer[_next].timestamp = millis();
    // } else {
    //     _buffer[_next].timestamp = &tagData.timestamp;
    // }
    
    // Inkrementer neste ledige indeks med wrap-around
    _next = (_next + 1) % _capacity;

    // Øk antall registreringer, men ikke over bufferSize
    if (_size < _capacity) {
        _size++;
    }
}

// Funksjon for å fjerne den eldste RFID-taggen fra ringbufferet (FIFO-prinsippet)
void RingBuffer::removeOldest() {
    // Sjekk om det er noen registreringer i bufferet
    if (_size > 0) {
        // Beregn indeksen til den eldste taggen
        int _oldest = (_next + _capacity - _size) % _capacity;

        // Nullstill dataene
        _buffer[_oldest] = {0};

        // Reduser antall registreringer
        _size--;    // holder seg positiv siden forutsetningen var _size > 0
        // _next = (_next + _capacity - 1) % _capacity;     // hvis next justeres ned så implementeres LIFO-struktur (stack)
    }
}

// Funksjon for å hente den eldste RFID-taggen fra ringbufferet
const RingBuffer::RFIDTag& RingBuffer::getOldest() const {
    // Sjekk om det er noen registreringer i bufferet
    if (_size > 0) {
        // Beregn indeksen til den eldste taggen
        int _oldest = (_next + _capacity - _size) % _capacity;

        // Returner referansen til den eldste taggen
        return _buffer[_oldest];
    } else {
        // Hvis det ikke er noen registreringer, returner en null-referanse
        return _buffer[0];
    }
}

// Funksjon for å skrive ut innholdet i ringbufferet
void RingBuffer::printAll() const {
    Serial.println("---- Ringbuffer ----");
    for (int i = 0; i < _size; i++) {
        int index = (_next + _capacity - _size + i) % _capacity;
        Serial.print("Index ");
        Serial.print(index);
        Serial.print(": ");
        for (int j = 0; j < 4; j++) {
            Serial.print(_buffer[index].data[j]);
            Serial.print(" ");
        }
        Serial.println(_buffer[index].timestamp);
    }
    Serial.println("--------------------");
}

// Funksjon for å returnere antall elementer i ringbufferet
const int RingBuffer::count() const {
    return _size;
}