#pragma once

#include <ESP8266WiFi.h>
#include <list>
#include <memory>
#include "config.h"

namespace homekit::wifi {

using homekit::config::ConfigData;

struct ScanResult {
    int rssi;
    String ssid;
};

void getConfig(ConfigData& cfg, const char** ssid, const char** psk, const char** hostname);

std::shared_ptr<std::list<ScanResult>> scan();

inline uint32_t getIPAsInteger() {
    if (!WiFi.isConnected())
        return 0;
    return WiFi.localIP().v4();
}

inline int8_t getRSSI() {
    return WiFi.RSSI();
}

extern const char AP_SSID[];
extern const char STA_SSID[];
extern const char STA_PSK[];
extern const char HOME_ID[];

}