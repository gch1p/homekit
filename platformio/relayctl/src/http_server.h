#pragma once
#include <ESP8266WebServer.h>
#include <Ticker.h>
#include <memory>
#include <list>
#include <utility>
#include "config.h"
#include "wifi.h"
#include "static.h"

namespace homekit {

struct OTAStatus {
    bool invalidMd5;

    OTAStatus() : invalidMd5(false) {}

    inline void clean() {
        invalidMd5 = false;
    }
};

using files::StaticFile;

class HttpServer {
private:
    ESP8266WebServer server;
    Ticker restartTimer;
    std::shared_ptr<std::list<wifi::ScanResult>> scanResults;
    OTAStatus ota;

    char* scanBuf;
    size_t scanBufSize;

    void sendGzip(const StaticFile& file, PGM_P content_type);
    void sendError(const String& message);

    bool getInputParam(const char* field_name, size_t max_len, String& dst);

public:
    explicit HttpServer(std::shared_ptr<std::list<wifi::ScanResult>> scanResults)
        : server(80)
        , scanResults(std::move(scanResults))
        , scanBufSize(512) {
        scanBuf = new char[scanBufSize];
    };

    ~HttpServer() {
        delete[] scanBuf;
    }

    void start();
    void loop();
};

}