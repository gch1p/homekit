#pragma once

namespace homekit {

inline size_t otaGetMaxUpdateSize() {
    return (ESP.getFreeSketchSpace() - 0x1000) & 0xFFFFF000;
}

inline void restart() {
    ESP.restart();
}

}