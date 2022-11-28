#pragma once

#include <Arduino.h>

namespace homekit {

class StopWatch {
private:
    unsigned long time;

public:
    StopWatch() : time(0) {};

    inline void save() {
        time = millis();
    }

    inline bool elapsed(unsigned long ms) {
        unsigned long now = millis();
        if (now < time) {
            // rollover?
            time = now;
        } else if (now - time >= ms) {
            return true;
        }
        return false;
    }
};

}