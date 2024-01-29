#include "../timer.h"
#include <Arduino.h>

Timer::Timer() {}

void Timer::setIdle() {
    _startTime = 0;
    _active = false;
}

void Timer::start() {
    _startTime = millis();
    _active = true;
}

unsigned long Timer::elapsedTime() const {          
    unsigned long currentTime = millis();
    return (currentTime - _startTime);
}

bool Timer::isActive() const {
    return _active;
}

unsigned long Timer::getMaxTime() const {
    return _maxTime;
}

void Timer::setMaxTime(unsigned long time) {
    _maxTime = time;
}
