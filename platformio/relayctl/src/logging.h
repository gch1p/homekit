#pragma once

#include <stdlib.h>
#include "config.def.h"

#ifdef DEBUG

#define PRINTLN(s)          Serial.println(s)
#define PRINT(s)            Serial.print(s)
#define PRINTF(fmt, ...)    Serial.printf(fmt, ##__VA_ARGS__)

#else

#define PRINTLN(s)
#define PRINT(s)
#define PRINTF(...)

#endif
