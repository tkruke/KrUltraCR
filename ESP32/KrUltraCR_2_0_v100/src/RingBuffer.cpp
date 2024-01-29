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

// Funksjon for å returnere Tag som en String 
// Endre format ved å angi TAG_FORMAT_DEC_FIXED, TAG_FORMAT_DEC_VAR eller TAG_FORMAT_HEX som andre parameter
String RingBuffer::getTagAsStr(const RFIDTag& tagData, int format) {
    char buf[20];  // Buffer for å lagre formatert streng

    switch(format) {
        case TAG_FORMAT_DEC_FIXED:
            snprintf(buf, sizeof(buf), "%03d-%03d-%03d-%03d", tagData.data[0], tagData.data[1], tagData.data[2], tagData.data[3]);
            break;
        case TAG_FORMAT_DEC_VAR:
            snprintf(buf, sizeof(buf), "%d-%d-%d-%d", tagData.data[0], tagData.data[1], tagData.data[2], tagData.data[3]);
            break;
        case TAG_FORMAT_HEX:
            snprintf(buf, sizeof(buf), "%02X-%02X-%02X-%02X", tagData.data[0], tagData.data[1], tagData.data[2], tagData.data[3]);
            break;
        default:
            return "Invalid format";  // Eller håndter feilformat på en annen måte
    }

    return String(buf);
}

// Funksjon for å returnere Tag som en String på default format dersom det ikke spesifiseres en parameter for format
String RingBuffer::getTagAsStr(const RFIDTag& tagData) {
    return getTagAsStr(tagData, TAG_FORMAT_DEFAULT);  // Kaller den opprinnelige funksjonen med standard format
}