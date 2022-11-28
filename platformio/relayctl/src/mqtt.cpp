#include "mqtt.h"
#include "logging.h"
#include "wifi.h"
#include "config.def.h"
#include "relay.h"
#include "config.h"

namespace homekit::mqtt {

static const uint8_t MQTT_CA_FINGERPRINT[] = DEFAULT_MQTT_CA_FINGERPRINT;
static const char MQTT_SERVER[] = DEFAULT_MQTT_SERVER;
static const uint16_t MQTT_PORT = DEFAULT_MQTT_PORT;
static const char MQTT_USERNAME[] = DEFAULT_MQTT_USERNAME;
static const char MQTT_PASSWORD[] = DEFAULT_MQTT_PASSWORD;
static const char MQTT_CLIENT_ID[] = DEFAULT_MQTT_CLIENT_ID;

static const char MQTT_SECRET[] = SECRET;
static const char TOPIC_RELAY_POWER[] = "relay/power";
static const char TOPIC_STAT[] = "stat";
static const char TOPIC_STAT1[] = "stat1";
static const char TOPIC_ADMIN[] = "admin";
static const char TOPIC_RELAY[] = "relay";


using namespace homekit;

MQTT::MQTT() : client(wifiClient) {
    randomSeed(micros());

    wifiClient.setFingerprint(MQTT_CA_FINGERPRINT);

    client.setServer(MQTT_SERVER, MQTT_PORT);
    client.setCallback([&](char* topic, byte* payload, unsigned int length)  {
        this->callback(topic, payload, length);
    });
}

void MQTT::connect() {
    reconnect();
}

void MQTT::reconnect() {
    char buf[128] {0};

    if (client.connected()) {
        PRINTLN("warning: already connected");
        return;
    }

    // Attempt to connect
    if (client.connect(MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
        PRINTLN("mqtt: connected");

        sendInitialStat();

        subscribe(TOPIC_RELAY);
        subscribe(TOPIC_ADMIN);
    } else {
        PRINTF("mqtt: failed to connect, rc=%d\n", client.state());
        wifiClient.getLastSSLError(buf, sizeof(buf));
        PRINTF("SSL error: %s\n", buf);

        reconnectTimer.once(2, [&]() {
            reconnect();
        });
    }
}

void MQTT::disconnect() {
    // TODO test how this works???
    reconnectTimer.detach();
    client.disconnect();
    wifiClient.stop();
}

bool MQTT::loop() {
    return client.loop();
}

bool MQTT::publish(const char* topic, uint8_t *payload, size_t length) {
    char full_topic[40] {0};
    strcpy(full_topic, "/hk/");
    strcat(full_topic, wifi::NODE_ID);
    strcat(full_topic, "/");
    strcat(full_topic, topic);
    return client.publish(full_topic, payload, length);
}

bool MQTT::subscribe(const char *topic) {
    char full_topic[40] {0};
    strcpy(full_topic, "/hk/");
    strcat(full_topic, wifi::NODE_ID);
    strcat(full_topic, "/");
    strcat(full_topic, topic);
    strcat(full_topic, "/#");
    bool res = client.subscribe(full_topic, 1);
    if (!res)
        PRINTF("error: failed to subscribe to %s\n", full_topic);
    return res;
}

void MQTT::sendInitialStat() {
    auto cfg = config::read();
    InitialStatPayload stat {
        .ip = wifi::getIPAsInteger(),
        .fw_version = FW_VERSION,
        .rssi = wifi::getRSSI(),
        .free_heap = ESP.getFreeHeap(),
        .flags = StatFlags {
            .state = static_cast<uint8_t>(relay::getState() ? 1 : 0),
            .config_changed_value_present = 1,
            .config_changed = static_cast<uint8_t>(cfg.flags.node_configured || cfg.flags.wifi_configured ? 1 : 0)
        }
    };
    publish(TOPIC_STAT1, reinterpret_cast<uint8_t*>(&stat), sizeof(stat));
    statStopWatch.save();
}

void MQTT::sendStat() {
    StatPayload stat {
            .rssi = wifi::getRSSI(),
            .free_heap = ESP.getFreeHeap(),
            .flags = StatFlags {
                    .state = static_cast<uint8_t>(relay::getState() ? 1 : 0),
                    .config_changed_value_present = 0,
                    .config_changed = 0
            }
    };

    PRINTF("free heap: %d\n", ESP.getFreeHeap());

    publish(TOPIC_STAT, reinterpret_cast<uint8_t*>(&stat), sizeof(stat));
    statStopWatch.save();
}

void MQTT::callback(char* topic, uint8_t* payload, uint32_t length) {
    const size_t bufsize = 16;
    char relevant_topic[bufsize];
    strncpy(relevant_topic, topic+strlen(wifi::NODE_ID)+5, bufsize);

    if (strncmp(TOPIC_RELAY_POWER, relevant_topic, bufsize) == 0) {
        handleRelayPowerPayload(payload, length);
    } else {
        PRINTF("error: invalid topic %s\n", topic);
    }
}

void MQTT::handleRelayPowerPayload(uint8_t *payload, uint32_t length) {
    if (length != sizeof(PowerPayload)) {
        PRINTF("error: size of payload (%ul) does not match expected (%ul)\n",
               length, sizeof(PowerPayload));
        return;
    }

    auto pd = reinterpret_cast<struct PowerPayload*>(payload);
    if (strncmp(pd->secret, MQTT_SECRET, sizeof(pd->secret)) != 0) {
        PRINTLN("error: invalid secret");
        return;
    }

    if (pd->state == 1) {
        relay::setOn();
    } else if (pd->state == 0) {
        relay::setOff();
    } else {
        PRINTLN("error: unexpected state value");
    }

    sendStat();
}

}