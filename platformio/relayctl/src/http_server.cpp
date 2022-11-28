#include <Arduino.h>
#include <string.h>

#include "http_server.h"
#include "config.h"
#include "wifi.h"
#include "config.def.h"
#include "logging.h"

namespace homekit {

static const char CONTENT_TYPE_HTML[] = "text/html; charset=utf-8";
static const char CONTENT_TYPE_CSS[] = "text/css";
static const char CONTENT_TYPE_JS[] = "application/javascript";
static const char CONTENT_TYPE_JSON[] = "application/json";
static const char CONTENT_TYPE_FAVICON[] = "image/x-icon";

static const char JSON_STATUS_FMT[] = "{\"node_id\":\"%s\""
#ifdef DEBUG
                                      ",\"configured\":%d"
                                      ",\"crc\":%u"
                                      ",\"fl_n\":%d"
                                      ",\"fl_w\":%d"
#endif
                                      "}";
static const size_t JSON_BUF_SIZE = 192;

static const char NODE_ID_ERROR[] = "?";

static const char FIELD_NODE_ID[] = "nid";
static const char FIELD_SSID[] = "ssid";
static const char FIELD_PSK[] = "psk";

static const char MSG_IS_INVALID[] = " is invalid";
static const char MSG_IS_MISSING[] = " is missing";

static const char GZIP[] = "gzip";
static const char CONTENT_ENCODING[] = "Content-Encoding";
static const char NOT_FOUND[] = "Not Found";

static void do_restart() {
    ESP.restart();
}

void HttpServer::start() {
    _server.on("/style.css", HTTP_GET, [](AsyncWebServerRequest* req) { sendGzip(req, files::style_css, CONTENT_TYPE_CSS); });
    _server.on("/app.js", HTTP_GET, [](AsyncWebServerRequest* req) { sendGzip(req, files::app_js, CONTENT_TYPE_JS); });
    _server.on("/favicon.ico", HTTP_GET, [](AsyncWebServerRequest* req) { sendGzip(req, files::favicon_ico, CONTENT_TYPE_FAVICON); });
    _server.on("/", HTTP_GET, [&](AsyncWebServerRequest* req) { sendGzip(req, files::index_html, CONTENT_TYPE_HTML); });

    _server.on("/status", HTTP_GET, [](AsyncWebServerRequest* req) {
        char json_buf[JSON_BUF_SIZE];
        auto cfg = config::read();
        char *ssid, *psk;
        wifi::getConfig(cfg, &ssid, &psk, nullptr);

        if (!isValid(cfg) || !cfg.flags.node_configured) {
            sprintf(json_buf, JSON_STATUS_FMT
                    , DEFAULT_NODE_ID
#ifdef DEBUG
                    , 0
                    , cfg.crc
                    , cfg.flags.node_configured
                    , cfg.flags.wifi_configured
#endif
            );
        } else {
            char escaped_node_id[32];
            char *escaped_node_id_res = cfg.escapeNodeId(escaped_node_id, 32);
            sprintf(json_buf, JSON_STATUS_FMT
                    , escaped_node_id_res == nullptr ? NODE_ID_ERROR : escaped_node_id
#ifdef DEBUG
                    , 1
                    , cfg.crc
                    , cfg.flags.node_configured
                    , cfg.flags.wifi_configured
#endif
            );
        }
        req->send(200, CONTENT_TYPE_JSON, json_buf);
    });

    _server.on("/status", HTTP_POST, [&](AsyncWebServerRequest* req) {
        auto cfg = config::read();
        char *s;

        if (!handleInputStr(req, FIELD_SSID, 32, &s)) return;
        strncpy(cfg.wifi_ssid, s, 32);
        PRINTF("saving ssid: %s\n", cfg.wifi_ssid);

        if (!handleInputStr(req, FIELD_PSK, 63, &s)) return;
        strncpy(cfg.wifi_psk, s, 63);
        PRINTF("saving psk: %s\n", cfg.wifi_psk);

        if (!handleInputStr(req, FIELD_NODE_ID, 16, &s)) return;
        strcpy(cfg.node_id, s);
        PRINTF("saving node id: %s\n", cfg.node_id);

        cfg.flags.node_configured = 1;
        cfg.flags.wifi_configured = 1;

        if (!config::write(cfg)) {
            PRINTLN("eeprom write error");
            return sendError(req, "eeprom error");
        }

        restartTimer.once(0, do_restart);
    });

    _server.on("/reset", HTTP_POST, [&](AsyncWebServerRequest* req) {
        config::erase();
        restartTimer.once(0, do_restart);
    });

    _server.on("/heap", HTTP_GET, [](AsyncWebServerRequest* req) {
       req->send(200, CONTENT_TYPE_HTML, String(ESP.getFreeHeap()));
    });

    _server.on("/scan", HTTP_GET, [&](AsyncWebServerRequest* req) {
        int i = 0;
        size_t len;
        const char* ssid;
        bool enough = false;

        bzero(reinterpret_cast<uint8_t*>(buf1k), ARRAY_SIZE(buf1k));
        char* cur = buf1k;

        strncpy(cur, "{\"list\":[", ARRAY_SIZE(buf1k));
        cur += 9;

        for (auto& res: *_scanResults) {
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

            if (cur - buf1k >= ARRAY_SIZE(buf1k)-40)
                enough = true;

            if (i < _scanResults->size()-1 || enough)
                *cur++ = ',';

            if (enough)
                break;

            i++;
        }

        *cur++ = ']';
        *cur++ = '}';
        *cur++ = '\0';

        req->send(200, CONTENT_TYPE_JSON, buf1k);
    });

    _server.on("/update", HTTP_POST, [&](AsyncWebServerRequest* req) {
        char json_buf[16];
        bool should_reboot = !Update.hasError();

        sprintf(json_buf, "{\"result\":%d}", should_reboot ? 1 : 0);

        auto resp = req->beginResponse(200, CONTENT_TYPE_JSON, json_buf);
        req->send(resp);

        if (should_reboot) restartTimer.once(1, do_restart);
    }, [&](AsyncWebServerRequest *req, const String& filename, size_t index, uint8_t *data, size_t len, bool final) {
        if (!index) {
            PRINTF("update start: %s\n", filename.c_str());
            Update.runAsync(true);
            if (!Update.begin((ESP.getFreeSketchSpace() - 0x1000) & 0xFFFFF000))
                Update.printError(Serial);
        }

        if (!Update.hasError() && len) {
            if (Update.write(data, len) != len) {
                Update.printError(Serial);
            }
        }

        if (final) { // if the final flag is set then this is the last frame of data
            if (Update.end(true)) {
                PRINTF("update success: %uB\n", index+len);
            } else {
                Update.printError(Serial);
            }
        }
    });

    _server.onNotFound([](AsyncWebServerRequest* req) {
        req->send(404, CONTENT_TYPE_HTML, NOT_FOUND);
    });

    _server.begin();
}

void HttpServer::sendGzip(AsyncWebServerRequest* req, StaticFile file, const char* content_type) {
    auto resp = req->beginResponse_P(200, content_type, file.content, file.size);
    resp->addHeader(CONTENT_ENCODING, GZIP);
    req->send(resp);
}

void HttpServer::sendError(AsyncWebServerRequest* req, const String& message) {
    char buf[32];
    if (snprintf(buf, 32, "error: %s", message.c_str()) == 32)
        buf[31] = '\0';
    req->send(400, CONTENT_TYPE_HTML, buf);
}

bool HttpServer::handleInputStr(AsyncWebServerRequest *req,
                                const char *field_name,
                                size_t max_len,
                                char **dst) {
    const char* s;
    size_t len;

    if (!req->hasParam(field_name, true)) {
        sendError(req, String(field_name) + String(MSG_IS_MISSING));
        return false;
    }

    s = req->getParam(field_name, true)->value().c_str();
    len = strlen(s);
    if (!len || len > max_len) {
        sendError(req, String(FIELD_NODE_ID) + String(MSG_IS_INVALID));
        return false;
    }

    *dst = (char*)s;
    return true;
}

}