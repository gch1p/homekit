#include <ESP8266httpUpdate.h>
#include "mqtt.h"
#include "logging.h"
#include "wifi.h"
#include "config.def.h"
#include "relay.h"
#include "config.h"
#include "static.h"
#include "util.h"
#include "led.h"

namespace homekit::mqtt {

static const uint8_t MQTT_CA_FINGERPRINT[] = DEFAULT_MQTT_CA_FINGERPRINT;
static const char MQTT_SERVER[] = DEFAULT_MQTT_SERVER;
static const uint16_t MQTT_PORT = DEFAULT_MQTT_PORT;
static const char MQTT_USERNAME[] = DEFAULT_MQTT_USERNAME;
static const char MQTT_PASSWORD[] = DEFAULT_MQTT_PASSWORD;
static const char MQTT_CLIENT_ID[] = DEFAULT_MQTT_CLIENT_ID;
static const char MQTT_SECRET[HOME_SECRET_SIZE+1] = HOME_SECRET;

static const char TOPIC_STAT[] = "stat";
static const char TOPIC_INITIAL_STAT[] = "stat1";
static const char TOPIC_OTA_RESPONSE[] = "otares";
static const char TOPIC_RELAY_POWER[] = "power";
static const char TOPIC_ADMIN_OTA[] = "admin/ota";
static const uint16_t MQTT_KEEPALIVE = 30;

enum class IncomingMessage {
    UNKNOWN,
    RELAY_POWER,
    OTA
};

using namespace espMqttClientTypes;

#define MD5_SIZE 16

MQTT::MQTT() {
    auto cfg = config::read();
    homeId = String(cfg.flags.node_configured ? cfg.home_id : wifi::HOME_ID);

    randomSeed(micros());

    client.onConnect([&](bool sessionPresent) {
        PRINTLN("mqtt: connected");

        sendInitialStat();

        subscribe(TOPIC_RELAY_POWER, 1);
        subscribe(TOPIC_ADMIN_OTA);
    });

    client.onDisconnect([&](DisconnectReason reason) {
        PRINTF("mqtt: disconnected, reason=%d\n", static_cast<int>(reason));
#ifdef DEBUG
        if (reason == DisconnectReason::TLS_BAD_FINGERPRINT)
            PRINTLN("reason: bad fingerprint");
#endif

        if (ota.started()) {
            PRINTLN("mqtt: update was in progress, canceling..");
            ota.clean();
            Update.end();
            Update.clearError();
        }

        if (ota.readyToRestart) {
            restartTimer.once(1, restart);
        } else {
            reconnectTimer.once(2, [&]() {
                reconnect();
            });
        }
    });

    client.onSubscribe([&](uint16_t packetId, const SubscribeReturncode* returncodes, size_t len) {
        PRINTF("mqtt: subscribe ack, packet_id=%d\n", packetId);
        for (size_t i = 0; i < len; i++) {
            PRINTF("    return code: %u\n", static_cast<unsigned int>(*(returncodes+i)));
        }
    });

    client.onUnsubscribe([&](uint16_t packetId) {
        PRINTF("mqtt: unsubscribe ack, packet_id=%d\n", packetId);
    });

    client.onMessage([&](const MessageProperties& properties, const char* topic, const uint8_t* payload, size_t len, size_t index, size_t total) {
        PRINTF("mqtt: message received, topic=%s, qos=%d, dup=%d, retain=%d, len=%ul, index=%ul, total=%ul\n",
               topic, properties.qos, (int)properties.dup, (int)properties.retain, len, index, total);

        IncomingMessage msgType = IncomingMessage::UNKNOWN;

        const char *ptr = topic + homeId.length() + 10;
        String relevantTopic(ptr);

        if (relevantTopic == TOPIC_RELAY_POWER)
            msgType = IncomingMessage::RELAY_POWER;
        else if (relevantTopic == TOPIC_ADMIN_OTA)
            msgType = IncomingMessage::OTA;

        if (len != total && msgType != IncomingMessage::OTA) {
            PRINTLN("mqtt: received partial message, not supported");
            return;
        }

        switch (msgType) {
        case IncomingMessage::RELAY_POWER:
            handleRelayPowerPayload(payload, total);
            break;

        case IncomingMessage::OTA:
            if (ota.finished)
                break;
            handleAdminOtaPayload(properties.packetId, payload, len, index, total);
            break;

        case IncomingMessage::UNKNOWN:
            PRINTF("error: invalid topic %s\n", topic);
            break;
        }
    });

    client.onPublish([&](uint16_t packetId) {
        PRINTF("mqtt: publish ack, packet_id=%d\n", packetId);

        if (ota.finished && packetId == ota.publishResultPacketId) {
            ota.readyToRestart = true;
        }
    });

    client.setServer(MQTT_SERVER, MQTT_PORT);
    client.setClientId(MQTT_CLIENT_ID);
    client.setCredentials(MQTT_USERNAME, MQTT_PASSWORD);
    client.setCleanSession(true);
    client.setFingerprint(MQTT_CA_FINGERPRINT);
    client.setKeepAlive(MQTT_KEEPALIVE);
}

void MQTT::connect() {
    reconnect();
}

void MQTT::reconnect() {
    if (client.connected()) {
        PRINTLN("warning: already connected");
        return;
    }
    client.connect();
}

void MQTT::disconnect() {
    // TODO test how this works???
    reconnectTimer.detach();
    client.disconnect();
}

uint16_t MQTT::publish(const String &topic, uint8_t *payload, size_t length) {
    String fullTopic = "hk/" + homeId + "/relay/" + topic;
    return client.publish(fullTopic.c_str(), 1, false, payload, length);
}

void MQTT::loop() {
    client.loop();
}

uint16_t MQTT::subscribe(const String &topic, uint8_t qos) {
    String fullTopic = "hk/" + homeId + "/relay/" + topic;
    PRINTF("mqtt: subscribing to %s...\n", fullTopic.c_str());

    uint16_t packetId = client.subscribe(fullTopic.c_str(), qos);
    if (!packetId)
        PRINTF("error: failed to subscribe to %s\n", fullTopic.c_str());
    return packetId;
}

void MQTT::sendInitialStat() {
    auto cfg = config::read();
    InitialStatPayload stat{
            .ip = wifi::getIPAsInteger(),
            .fw_version = FW_VERSION,
            .rssi = wifi::getRSSI(),
            .free_heap = ESP.getFreeHeap(),
            .flags = StatFlags{
                    .state = static_cast<uint8_t>(relay::getState() ? 1 : 0),
                    .config_changed_value_present = 1,
                    .config_changed = static_cast<uint8_t>(cfg.flags.node_configured ||
                                                           cfg.flags.wifi_configured ? 1 : 0)
            }
    };
    publish(TOPIC_INITIAL_STAT, reinterpret_cast<uint8_t*>(&stat), sizeof(stat));
    statStopWatch.save();
}

void MQTT::sendStat() {
    StatPayload stat{
            .rssi = wifi::getRSSI(),
            .free_heap = ESP.getFreeHeap(),
            .flags = StatFlags{
                    .state = static_cast<uint8_t>(relay::getState() ? 1 : 0),
                    .config_changed_value_present = 0,
                    .config_changed = 0
            }
    };
    publish(TOPIC_STAT, reinterpret_cast<uint8_t*>(&stat), sizeof(stat));
    statStopWatch.save();
}

uint16_t MQTT::sendOtaResponse(OTAResult status, uint8_t error_code) {
    OTAResponse resp{
            .status = status,
            .error_code = error_code
    };
    return publish(TOPIC_OTA_RESPONSE, reinterpret_cast<uint8_t*>(&resp), sizeof(resp));
}

void MQTT::handleRelayPowerPayload(const uint8_t *payload, uint32_t length) {
    if (length != sizeof(PowerPayload)) {
        PRINTF("error: size of payload (%ul) does not match expected (%ul)\n",
               length, sizeof(PowerPayload));
        return;
    }

    auto pd = reinterpret_cast<const struct PowerPayload*>(payload);
    if (strncmp(pd->secret, MQTT_SECRET, sizeof(pd->secret)) != 0) {
        PRINTLN("error: invalid secret");
        return;
    }

    if (pd->state == 1) {
        PRINTLN("mqtt: turning relay on");
        relay::setOn();
    } else if (pd->state == 0) {
        PRINTLN("mqtt: turning relay off");
        relay::setOff();
    } else {
        PRINTLN("error: unexpected state value");
    }

    sendStat();
}

void MQTT::handleAdminOtaPayload(uint16_t packetId, const uint8_t *payload, size_t length, size_t index, size_t total) {
    char md5[33];
    char* md5Ptr = md5;

    if (index != 0 && ota.dataPacketId != packetId) {
        PRINTLN("mqtt/ota: non-matching packet id");
        return;
    }

    Update.runAsync(true);

    if (index == 0) {
        if (length < HOME_SECRET_SIZE + MD5_SIZE) {
            PRINTLN("mqtt/ota: failed to check secret, first packet size is too small");
            return;
        }

        if (memcmp((const char*)payload, HOME_SECRET, HOME_SECRET_SIZE) != 0) {
            PRINTLN("mqtt/ota: invalid secret");
            return;
        }

        PRINTF("mqtt/ota: starting update, total=%ul\n", total-HOME_SECRET_SIZE);
        for (int i = 0; i < MD5_SIZE; i++) {
            md5Ptr += sprintf(md5Ptr, "%02x", *((unsigned char*)(payload+HOME_SECRET_SIZE+i)));
        }
        md5[32] = '\0';
        PRINTF("mqtt/ota: md5 is %s\n", md5);
        PRINTF("mqtt/ota: first packet is %ul bytes length\n", length);

        md5[32] = '\0';

        if (Update.isRunning()) {
            Update.end();
            Update.clearError();
        }

        if (!Update.setMD5(md5)) {
            PRINTLN("mqtt/ota: setMD5 failed");
            return;
        }

        ota.dataPacketId = packetId;

        if (!Update.begin(total - HOME_SECRET_SIZE - MD5_SIZE)) {
            ota.clean();
#ifdef DEBUG
            Update.printError(Serial);
#endif
            sendOtaResponse(OTAResult::UPDATE_ERROR, Update.getError());
        }

        ota.written = Update.write(const_cast<uint8_t*>(payload)+HOME_SECRET_SIZE + MD5_SIZE, length-HOME_SECRET_SIZE - MD5_SIZE);
        ota.written += HOME_SECRET_SIZE + MD5_SIZE;

        esp_led.blink(1, 1);
        PRINTF("mqtt/ota: updating %u/%u\n", ota.written, Update.size());

    } else {
        if (!Update.isRunning()) {
            PRINTLN("mqtt/ota: update is not running");
            return;
        }

        if (index == ota.written) {
            size_t written;
            if ((written = Update.write(const_cast<uint8_t*>(payload), length)) != length) {
                PRINTF("mqtt/ota: error: tried to write %ul bytes, write() returned %ul\n",
                        length, written);
                ota.clean();
                Update.end();
                Update.clearError();
                sendOtaResponse(OTAResult::WRITE_ERROR);
                return;
            }
            ota.written += length;

            esp_led.blink(1, 1);
            PRINTF("mqtt/ota: updating %u/%u\n",
                   ota.written - HOME_SECRET_SIZE - MD5_SIZE,
                   Update.size());
        } else {
            PRINTF("mqtt/ota: position is invalid, expected %ul, got %ul\n", ota.written, index);
            ota.clean();
            Update.end();
            Update.clearError();
        }
    }

    if (Update.isFinished()) {
        ota.dataPacketId = 0;

        if (Update.end()) {
            ota.finished = true;
            ota.publishResultPacketId = sendOtaResponse(OTAResult::OK);
            PRINTF("mqtt/ota: ok, otares packet_id=%d\n", ota.publishResultPacketId);
        } else {
            ota.clean();

            PRINTF("mqtt/ota: error: %u\n", Update.getError());
#ifdef DEBUG
            Update.printError(Serial);
#endif
            Update.clearError();

            sendOtaResponse(OTAResult::UPDATE_ERROR, Update.getError());
        }
    }
}

}