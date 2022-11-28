#include "led.h"

namespace homekit {

void Led::blink(uint8_t count, uint16_t delay_ms) const {
    for (uint8_t i = 0; i < count; i++) {
        on_off(delay_ms, i < count-1);
    }
}

void Led::on_off(uint16_t delay_ms, bool last_delay) const {
    on();
    delay(delay_ms);

    off();
    if (last_delay)
        delay(delay_ms);
}

}