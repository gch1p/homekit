#include <Arduino.h>
#include <string.h>

#include "static.h"
#include "http_server.h"
#include "config.h"
#include "config.def.h"
#include "logging.h"
#include "util.h"
#include "led.h"

namespace homekit {

using files::StaticFile;

static const char CONTENT_TYPE_HTML[] PROGMEM = "text/html; charset=utf-8";
static const char CONTENT_TYPE_CSS[] PROGMEM = "text/css";
static const char CONTENT_TYPE_JS[] PROGMEM = "application/javascript";
static const char CONTENT_TYPE_JSON[] PROGMEM = "application/json";
static const char CONTENT_TYPE_FAVICON[] PROGMEM = "image/x-icon";

static const char JSON_UPDATE_FMT[] PROGMEM = "{\"result\":%d}";
static const char JSON_STATUS_FMT[] PROGMEM = "{\"home_id\":\"%s\""
#ifdef DEBUG
                                      ",\"configured\":%d"
                                      ",\"crc\":%u"
                                      ",\"fl_n\":%d"
                                      ",\"fl_w\":%d"
#endif
                                      "}";
static const size_t JSON_BUF_SIZE = 192;

static const char JSON_SCAN_FIRST_LIST[] PROGMEM = "{\"list\":[";

static const char MSG_IS_INVALID[] PROGMEM = " is invalid";
static const char MSG_IS_MISSING[] PROGMEM = " is missing";

static const char GZIP[] PROGMEM = "gzip";
static const char CONTENT_ENCODING[] PROGMEM = "Content-Encoding";
static const char NOT_FOUND[] PROGMEM = "Not Found";

static const char ROUTE_STYLE_CSS[] PROGMEM = "/style.css";
static const char ROUTE_APP_JS[] PROGMEM = "/app.js";
static const char ROUTE_MD5_JS[] PROGMEM = "/md5.js";
static const char ROUTE_FAVICON_ICO[] PROGMEM = "/favicon.ico";
static const char ROUTE_STATUS[] PROGMEM = "/status";
static const char ROUTE_SCAN[] PROGMEM = "/scan";
static const char ROUTE_RESET[] PROGMEM = "/reset";
// #ifdef DEBUG
static const char ROUTE_HEAP[] PROGMEM = "/heap";
// #endif
static const char ROUTE_UPDATE[] PROGMEM = "/update";

void HttpServer::start() {
    server.on(FPSTR(ROUTE_STYLE_CSS), HTTP_GET, [&]() { sendGzip(files::style_css, CONTENT_TYPE_CSS); });
    server.on(FPSTR(ROUTE_APP_JS), HTTP_GET, [&]() { sendGzip(files::app_js, CONTENT_TYPE_JS); });
    server.on(FPSTR(ROUTE_MD5_JS), HTTP_GET, [&]() { sendGzip(files::md5_js, CONTENT_TYPE_JS); });
    server.on(FPSTR(ROUTE_FAVICON_ICO), HTTP_GET, [&]() { sendGzip(files::favicon_ico, CONTENT_TYPE_FAVICON); });

    server.on("/", HTTP_GET, [&]() { sendGzip(files::index_html, CONTENT_TYPE_HTML); });
    server.on(FPSTR(ROUTE_STATUS), HTTP_GET, [&]() {
        char json_buf[JSON_BUF_SIZE];
        auto cfg = config::read();

        if (!isValid(cfg) || !cfg.flags.node_configured) {
            sprintf_P(json_buf, JSON_STATUS_FMT
                    , DEFAULT_HOME_ID
#ifdef DEBUG
                    , 0
                    , cfg.crc
                    , cfg.flags.node_configured
                    , cfg.flags.wifi_configured
#endif
            );
        } else {
            char escaped_home_id[32];
            char *escaped_home_id_res = cfg.escapeHomeId(escaped_home_id, 32);
            sprintf_P(json_buf, JSON_STATUS_FMT
                    , escaped_home_id_res == nullptr ? "?" : escaped_home_id
#ifdef DEBUG
                    , 1
                    , cfg.crc
                    , cfg.flags.node_configured
                    , cfg.flags.wifi_configured
#endif
            );
        }
        server.send(200, FPSTR(CONTENT_TYPE_JSON), json_buf);
    });
    server.on(FPSTR(ROUTE_STATUS), HTTP_POST, [&]() {
        auto cfg = config::read();
        String s;

        if (!getInputParam("ssid", 32, s)) return;
        strncpy(cfg.wifi_ssid, s.c_str(), 32);
        PRINTF("saving ssid: %s\n", cfg.wifi_ssid);

        if (!getInputParam("psk", 63, s)) return;
        strncpy(cfg.wifi_psk, s.c_str(), 63);
        PRINTF("saving psk: %s\n", cfg.wifi_psk);

        if (!getInputParam("hid", 16, s)) return;
        strcpy(cfg.home_id, s.c_str());
        PRINTF("saving home id: %s\n", cfg.home_id);

        cfg.flags.node_configured = 1;
        cfg.flags.wifi_configured = 1;

        config::write(cfg);

        restartTimer.once(0, restart);
    });

    server.on(FPSTR(ROUTE_RESET), HTTP_POST, [&]() {
        config::erase();
        restartTimer.once(1, restart);
    });

    server.on(FPSTR(ROUTE_HEAP), HTTP_GET, [&]() {
       server.send(200, FPSTR(CONTENT_TYPE_HTML), String(ESP.getFreeHeap()));
    });

    server.on(FPSTR(ROUTE_SCAN), HTTP_GET, [&]() {
        size_t i = 0;
        size_t len;
        const char* ssid;
        bool enough = false;

        bzero(reinterpret_cast<uint8_t*>(scanBuf), scanBufSize);
        char* cur = scanBuf;

        strncpy_P(cur, JSON_SCAN_FIRST_LIST, scanBufSize);
        cur += 9;

        for (auto& res: *scanResults) {
            ssid = res.ssid.c_str();
            len = res.ssid.length();

            // new item (array with 2 items)
            *cur++ = '[';

            // 1. ssid (string)
            *cur++ = '"';
            for (size_t j = 0; j < len; j++) {
                if (*(ssid+j) == '"')
                    *cur++ = '\\';
                *cur++ = *(ssid+j);
            }
            *cur++ = '"';
            *cur++ = ',';

            // 2. rssi (number)
            cur += sprintf(cur, "%d", res.rssi);

            // close array
            *cur++ = ']';

            if ((size_t)(cur - scanBuf) >= (size_t) ARRAY_SIZE(scanBuf) - 40)
                enough = true;

            if (i < scanResults->size() - 1 || enough)
                *cur++ = ',';

            if (enough)
                break;

            i++;
        }

        *cur++ = ']';
        *cur++ = '}';
        *cur++ = '\0';

        server.send(200, FPSTR(CONTENT_TYPE_JSON), scanBuf);
    });

    server.on(FPSTR(ROUTE_UPDATE), HTTP_POST, [&]() {
        char json_buf[16];
        bool should_reboot = !Update.hasError() && !ota.invalidMd5;
        Update.clearError();

        sprintf_P(json_buf, JSON_UPDATE_FMT, should_reboot ? 1 : 0);

        server.send(200, FPSTR(CONTENT_TYPE_JSON), json_buf);

        if (should_reboot)
            restartTimer.once(1, restart);
    }, [&]() {
        HTTPUpload& upload = server.upload();

        if (upload.status == UPLOAD_FILE_START) {
            ota.clean();

            String s;
            if (!getInputParam("md5", 0, s)) {
                ota.invalidMd5 = true;
                PRINTLN("http/ota: md5 not found");
                return;
            }

            if (!Update.setMD5(s.c_str())) {
                ota.invalidMd5 = true;
                PRINTLN("http/ota: setMD5() failed");
                return;
            }

            Serial.printf("http/ota: starting, filename=%s\n", upload.filename.c_str());
            if (!Update.begin(otaGetMaxUpdateSize())) {
#ifdef DEBUG
                Update.printError(Serial);
#endif
            }
        } else if (upload.status == UPLOAD_FILE_WRITE) {
            if (!Update.isRunning())
                return;

            PRINTF("http/ota: writing %ul\n", upload.currentSize);
            esp_led.blink(1, 1);
            if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
#ifdef DEBUG
                Update.printError(Serial);
#endif
            }
        } else if (upload.status == UPLOAD_FILE_END) {
            if (!Update.isRunning())
                return;

            if (Update.end(true)) {
                PRINTF("http/ota: ok, total size %ul\n", upload.totalSize);
            } else {
#ifdef DEBUG
                Update.printError(Serial);
#endif
            }
        }
    });

    server.onNotFound([&]() {
        server.send(404, FPSTR(CONTENT_TYPE_HTML), NOT_FOUND);
    });

    server.begin();
}

void HttpServer::loop() {
    server.handleClient();
}

void HttpServer::sendGzip(const StaticFile& file, PGM_P content_type) {
    server.sendHeader(FPSTR(CONTENT_ENCODING), FPSTR(GZIP));
    server.send_P(200, content_type, (const char*)file.content, file.size);
}

void HttpServer::sendError(const String& message) {
    char buf[32];
    if (snprintf_P(buf, 32, PSTR("error: %s"), message.c_str()) == 32)
        buf[31] = '\0';
    server.send(400, FPSTR(CONTENT_TYPE_HTML), buf);
}

bool HttpServer::getInputParam(const char *field_name,
                               size_t max_len,
                               String& dst) {
    if (!server.hasArg(field_name)) {
        sendError(String(field_name) + String(MSG_IS_MISSING));
        return false;
    }

    String field = server.arg(field_name);
    if (!field.length() || (max_len != 0 && field.length() > max_len)) {
        sendError(String(field_name) + String(MSG_IS_INVALID));
        return false;
    }

    dst = field;
    return true;
}

}