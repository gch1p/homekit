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

void getConfig(ConfigData &cfg, char **ssid_dst, char **psk_dst, char **hostname_dst);
std::shared_ptr<std::list<ScanResult>> scan();

inline int8_t getRSSI() {
    return WiFi.RSSI();
}

inline uint32_t getIPAsInteger() {
    if (!WiFi.isConnected())
        return 0;
    return WiFi.localIP().v4();
}

extern const char WIFI_AP_SSID[];
extern const char WIFI_STA_SSID[];
extern const char WIFI_STA_PSK[];
extern const char NODE_ID[];

}