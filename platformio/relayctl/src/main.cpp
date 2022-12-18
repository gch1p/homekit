#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <DNSServer.h>
#include <Ticker.h>

#include "mqtt.h"
#include "config.h"
#include "logging.h"
#include "http_server.h"
#include "led.h"
#include "config.def.h"
#include "wifi.h"
#include "relay.h"
#include "stopwatch.h"

using namespace homekit;

enum class WorkingMode {
    RECOVERY, // AP mode, http server with configuration
    NORMAL,   // MQTT client
};
static enum WorkingMode working_mode = WorkingMode::NORMAL;

enum class WiFiConnectionState {
    WAITING = 0,
    JUST_CONNECTED = 1,
    CONNECTED = 2
};

static const uint16_t recovery_boot_detection_ms = 2000;
static const uint8_t recovery_boot_delay_ms = 100;

static volatile enum WiFiConnectionState wifi_state = WiFiConnectionState::WAITING;
static void* service = nullptr;
static WiFiEventHandler wifiConnectHandler, wifiDisconnectHandler;
static Ticker wifiTimer;
static StopWatch blinkStopWatch;

static DNSServer* dnsServer = nullptr;

static void onWifiConnected(const WiFiEventStationModeGotIP& event);
static void onWifiDisconnected(const WiFiEventStationModeDisconnected& event);

static void wifiConnect() {
    const char *ssid, *psk, *hostname;
    auto cfg = config::read();
    wifi::getConfig(cfg, &ssid, &psk, &hostname);

    PRINTF("Wi-Fi STA creds: ssid=%s, psk=%s, hostname=%s\n", ssid, psk, hostname);

    wifi_state = WiFiConnectionState::WAITING;

    WiFi.mode(WIFI_STA);
    WiFi.hostname(hostname);
    WiFi.begin(ssid, psk);

    PRINT("connecting to wifi..");
}

static void wifiHotspot() {
    esp_led.on();

    auto scanResults = wifi::scan();

    WiFi.mode(WIFI_AP);
    WiFi.softAP(wifi::AP_SSID);

    dnsServer = new DNSServer();
    dnsServer->start(53, "*", WiFi.softAPIP());

    service = new HttpServer(scanResults);
    ((HttpServer*)service)->start();
}

void setup() {
    WiFi.disconnect();

#ifdef DEBUG
    Serial.begin(115200);
#endif

    relay::init();

    pinMode(FLASH_BUTTON_PIN, INPUT_PULLUP);
    for (uint16_t i = 0; i < recovery_boot_detection_ms; i += recovery_boot_delay_ms) {
        delay(recovery_boot_delay_ms);
        if (digitalRead(FLASH_BUTTON_PIN) == LOW) {
            working_mode = WorkingMode::RECOVERY;
            break;
        }
    }

    auto cfg = config::read();
    if (config::isDirty(cfg)) {
        PRINTLN("config is dirty, erasing...");
        config::erase(cfg);
        board_led.blink(10, 50);
    }

    switch (working_mode) {
    case WorkingMode::RECOVERY:
        wifiHotspot();
        break;

    case WorkingMode::NORMAL:
        wifiConnectHandler = WiFi.onStationModeGotIP(onWifiConnected);
        wifiDisconnectHandler = WiFi.onStationModeDisconnected(onWifiDisconnected);
        wifiConnect();
        break;
    }
}

void loop() {
    if (working_mode == WorkingMode::NORMAL) {
        if (wifi_state == WiFiConnectionState::WAITING) {
            PRINT(".");
            esp_led.blink(2, 50);
            delay(1000);
            return;
        }

        if (wifi_state == WiFiConnectionState::JUST_CONNECTED) {
            board_led.blink(3, 300);
            wifi_state = WiFiConnectionState::CONNECTED;

            if (service == nullptr)
                service = new mqtt::MQTT();

            ((mqtt::MQTT*)service)->connect();
            blinkStopWatch.save();
        }

        auto mqtt = (mqtt::MQTT*)service;
        if (static_cast<int>(wifi_state) >= 1 && mqtt != nullptr) {
            mqtt->loop();

            if (mqtt->ota.readyToRestart) {
                mqtt->disconnect();
            } else if (mqtt->statStopWatch.elapsed(10000)) {
                mqtt->sendStat();
            }

            // periodically blink board led
            if (blinkStopWatch.elapsed(5000)) {
                // PRINTF("free heap: %d\n", ESP.getFreeHeap());
                board_led.blink(1, 10);
                blinkStopWatch.save();
            }
        }
    } else {
        if (dnsServer != nullptr)
            dnsServer->processNextRequest();

        auto httpServer = (HttpServer*)service;
        if (httpServer != nullptr)
            httpServer->loop();
    }
}

static void onWifiConnected(const WiFiEventStationModeGotIP& event) {
    PRINTF("connected (%s)\n", WiFi.localIP().toString().c_str());
    wifi_state = WiFiConnectionState::JUST_CONNECTED;
}

static void onWifiDisconnected(const WiFiEventStationModeDisconnected& event) {
    PRINTLN("disconnected from wi-fi");
    wifi_state = WiFiConnectionState::WAITING;
    if (service != nullptr)
        ((mqtt::MQTT*)service)->disconnect();
    wifiTimer.once(2, wifiConnect);
}