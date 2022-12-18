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

    void on_off(uint16_t delay_ms, bool last_delay = false) const {
        on();
        delay(delay_ms);

        off();
        if (last_delay)
            delay(delay_ms);
    }

    void blink(uint8_t count, uint16_t delay_ms) const {
        for (uint8_t i = 0; i < count; i++) {
            on_off(delay_ms, i < count-1);
        }
    }
};

extern Led board_led;
extern Led esp_led;

}