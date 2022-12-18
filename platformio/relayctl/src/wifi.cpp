#include <pgmspace.h>
#include "config.def.h"
#include "wifi.h"
#include "config.h"
#include "logging.h"

namespace homekit::wifi {

using namespace homekit;
using homekit::config::ConfigData;

const char HOME_ID[] = DEFAULT_HOME_ID;
const char AP_SSID[] = DEFAULT_WIFI_AP_SSID;
const char STA_SSID[] = DEFAULT_WIFI_STA_SSID;
const char STA_PSK[] = DEFAULT_WIFI_STA_PSK;

void getConfig(ConfigData &cfg, const char** ssid, const char** psk, const char** hostname) {
    if (cfg.flags.wifi_configured) {
        *ssid = cfg.wifi_ssid;
        *psk = cfg.wifi_psk;
        *hostname = cfg.home_id;
    } else {
        *ssid = STA_SSID;
        *psk = STA_PSK;
        *hostname = HOME_ID;
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