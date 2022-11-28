#pragma once

#include <Arduino.h>

namespace homekit::config {

struct ConfigFlags {
    uint8_t wifi_configured: 1;
    uint8_t node_configured: 1;
    uint8_t reserved: 6;
} __attribute__((packed));

struct ConfigData {
    // helpers
    uint32_t crc = 0;
    uint32_t magic = 0;
    char node_id[16] = {0};
    char wifi_ssid[32] = {0};
    char wifi_psk[63] = {0};
    ConfigFlags flags {0};

    // helper methods
    char* escapeNodeId(char* buf, size_t len);
} __attribute__((packed));


ConfigData read();
bool write(ConfigData& data);
bool erase();
bool erase(ConfigData& data);
bool isValid(ConfigData& data);
bool isDirty(ConfigData& data);

}