#include <ESP8266WiFi.h>
#include <espMqttClient.h>
#include <Ticker.h>
#include "stopwatch.h"

namespace homekit { namespace mqtt {

enum class OTAResult: uint8_t {
    OK = 0,
    UPDATE_ERROR = 1,
    WRITE_ERROR = 2,
};

struct OTAStatus {
    uint16_t dataPacketId;
    uint16_t publishResultPacketId;
    bool finished;
    bool readyToRestart;
    size_t written;

    OTAStatus()
        : dataPacketId(0)
        , publishResultPacketId(0)
        , finished(false)
        , readyToRestart(false)
        , written(0)
    {}

    inline void clean() {
        dataPacketId = 0;
        publishResultPacketId = 0;
        finished = false;
        readyToRestart = false;
        written = 0;
    }

    inline bool started() const {
        return dataPacketId != 0;
    }
};

class MQTT {
private:
    String homeId;
    WiFiClientSecure httpsSecureClient;
    espMqttClientSecure client;
    Ticker reconnectTimer;
    Ticker restartTimer;

    void handleRelayPowerPayload(const uint8_t* payload, uint32_t length);
    void handleAdminOtaPayload(uint16_t packetId, const uint8_t* payload, size_t length, size_t index, size_t total);

    uint16_t publish(const String& topic, uint8_t* payload, size_t length);
    uint16_t subscribe(const String& topic, uint8_t qos = 0);
    void sendInitialStat();
    uint16_t sendOtaResponse(OTAResult status, uint8_t error_code = 0);

public:
    StopWatch statStopWatch;
    OTAStatus ota;

    MQTT();
    void connect();
    void disconnect();
    void reconnect();
    void loop();
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

struct OTAResponse {
    OTAResult status;
    uint8_t error_code;
} __attribute__((packed));

} }