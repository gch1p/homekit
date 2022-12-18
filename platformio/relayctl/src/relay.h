#pragma once

#include <Arduino.h>
#include "config.def.h"

namespace homekit { namespace relay {

inline void init() {
    pinMode(RELAY_PIN, OUTPUT);
}

inline bool getState() {
    return digitalRead(RELAY_PIN) == HIGH;
}

inline void setOn() {
    digitalWrite(RELAY_PIN, HIGH);
}

inline void setOff() {
    digitalWrite(RELAY_PIN, LOW);
}

} }