#pragma once

#include <stdlib.h>
#include "config.def.h"

#ifdef DEBUG

namespace homekit {
void hexdump(const void* data, size_t size);
}

#define PRINTLN(s)          Serial.println(s)
#define PRINT(s)            Serial.print(s)
#define PRINTF(fmt, ...)    Serial.printf(fmt, ##__VA_ARGS__)
#define HEXDUMP(data, size) homekit::hexdump((data), (size));

#else

#define PRINTLN(s)
#define PRINT(s)
#define PRINTF(a)
#define HEXDUMP(data, size)

#endif
