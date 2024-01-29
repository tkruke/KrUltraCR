#ifndef TIMER_H
#define TIMER_H

class Timer {
private:
    bool _active = false;
    unsigned long _startTime = 0;
    unsigned long _maxTime = 0;

public:
    Timer();

    void setIdle();
    void start();
    unsigned long elapsedTime() const;

    bool isActive() const;
    unsigned long getMaxTime() const;
    void setMaxTime(unsigned long time);
};

#endif // TIMER_H
