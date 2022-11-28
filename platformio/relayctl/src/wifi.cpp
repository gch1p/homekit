#include "config.def.h"
#include "wifi.h"
#include "config.h"
#include "logging.h"

namespace homekit::wifi {

using namespace homekit;
using homekit::config::ConfigData;

const char NODE_ID[] = DEFAULT_NODE_ID;
const char WIFI_AP_SSID[] = DEFAULT_WIFI_AP_SSID;
const char WIFI_STA_SSID[] = DEFAULT_WIFI_STA_SSID;
const char WIFI_STA_PSK[] = DEFAULT_WIFI_STA_PSK;

void getConfig(ConfigData& cfg, char** ssid_dst, char** psk_dst, char** hostname_dst) {
    if (cfg.flags.wifi_configured) {
        *ssid_dst = cfg.wifi_ssid;
        *psk_dst = cfg.wifi_psk;
        if (hostname_dst != nullptr)
            *hostname_dst = cfg.node_id;
    } else {
        *ssid_dst = (char*)WIFI_STA_SSID;
        *psk_dst = (char*)WIFI_STA_PSK;
        if (hostname_dst != nullptr)
            *hostname_dst = (char*)NODE_ID;
    }
}

std::shared_ptr<std::list<ScanResult>> scan() {
    if (WiFi.getMode() != WIFI_STA) {
        PRINTLN("wifi::scan: switching mode to STA");
        WiFi.mode(WIFI_STA);
    }

    std::shared_ptr<std::list<ScanResult>> results(new std::list<ScanResult>);
    int count = WiFi.scanNetworks();
    for (int i = 0; i < count; i++) {
        results->push_back(ScanResult {
            .rssi = WiFi.RSSI(i),
            .ssid = WiFi.SSID(i)
        });
    }

    WiFi.scanDelete();
    return results;
}

}