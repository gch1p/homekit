#include "led.h"
#include "config.def.h"

namespace homekit {

Led board_led(BOARD_LED_PIN);
Led esp_led(ESP_LED_PIN);

}