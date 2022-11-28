#pragma once

#include <Arduino.h>

namespace homekit {

class Led {
private:
    uint8_t _pin;

public:
    explicit Led(uint8_t pin) : _pin(pin) {
        pinMode(_pin, OUTPUT);
        off();
    }

    inline void off() const { digitalWrite(_pin, HIGH); }
    inline void on() const { digitalWrite(_pin, LOW); }

    void on_off(uint16_t delay_ms, bool last_delay = false) const;
    void blink(uint8_t count, uint16_t delay_ms) const;
};

}