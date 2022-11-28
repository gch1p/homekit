#pragma once

#include <memory>
#include <list>
#include <Ticker.h>
#include <utility>
#include <ESPAsyncWebServer.h>
#include "static.h"
#include "config.h"
#include "wifi.h"

namespace homekit {

using files::StaticFile;

class HttpServer {
private:
    AsyncWebServer _server;
    Ticker restartTimer;
    std::shared_ptr<std::list<wifi::ScanResult>> _scanResults;
    char buf1k[1024];

    static void sendGzip(AsyncWebServerRequest* req, StaticFile file, const char* content_type);
    static void sendError(AsyncWebServerRequest* req, const String& message);

    static bool handleInputStr(AsyncWebServerRequest* req, const char* field_name, size_t max_len, char** dst);
    // static bool handle_input_addr(AsyncWebServerRequest* req, const char* field_name, ConfigIPv4Addr* addr_dst);

public:
    explicit HttpServer(std::shared_ptr<std::list<wifi::ScanResult>> scanResults)
        : _server(80)
        , _scanResults(std::move(scanResults)) {};

    void start();
};

}