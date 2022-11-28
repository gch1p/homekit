#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Ticker.h>
#include "stopwatch.h"

namespace homekit::mqtt {

class MQTT {
private:
    WiFiClientSecure wifiClient;
    PubSubClient client;
    Ticker reconnectTimer;

    void callback(char* topic, uint8_t* payload, size_t length);
    void handleRelayPowerPayload(uint8_t* payload, uint32_t length);
    bool publish(const char* topic, uint8_t* payload, size_t length);
    bool subscribe(const char* topic);
    void sendInitialStat();

public:
    StopWatch statStopWatch;

    MQTT();
    void connect();
    void disconnect();
    void reconnect();
    bool loop();
    void sendStat();
};

struct StatFlags {
    uint8_t state: 1;
    uint8_t config_changed_value_present: 1;
    uint8_t config_changed: 1;
    uint8_t reserved: 5;
} __attribute__((packed));

struct InitialStatPayload {
    uint32_t ip;
    uint8_t fw_version;
    int8_t rssi;
    uint32_t free_heap;
    StatFlags flags;
} __attribute__((packed));

struct StatPayload {
    int8_t rssi;
    uint32_t free_heap;
    StatFlags flags;
} __attribute__((packed));

struct PowerPayload {
    char secret[12];
    uint8_t state;
} __attribute__((packed));

}