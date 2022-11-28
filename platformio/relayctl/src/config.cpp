#include <EEPROM.h>
#include <strings.h>
#include "config.h"
#include "config.def.h"
#include "logging.h"

#define GET_DATA_CRC(data) \
    eeprom_crc(reinterpret_cast<uint8_t*>(&(data))+4, sizeof(ConfigData)-4)

namespace homekit::config {

static const uint32_t magic = 0xdeadbeef;
static const uint32_t crc_table[16] = {
        0x00000000, 0x1db71064, 0x3b6e20c8, 0x26d930ac,
        0x76dc4190, 0x6b6b51f4, 0x4db26158, 0x5005713c,
        0xedb88320, 0xf00f9344, 0xd6d6a3e8, 0xcb61b38c,
        0x9b64c2b0, 0x86d3d2d4, 0xa00ae278, 0xbdbdf21c
};

static uint32_t eeprom_crc(const uint8_t* data, size_t len) {
    uint32_t crc = ~0L;
    for (size_t index = 0; index < len; index++) {
        crc = crc_table[(crc ^ data[index]) & 0x0f] ^ (crc >> 4);
        crc = crc_table[(crc ^ (data[index] >> 4)) & 0x0f] ^ (crc >> 4);
        crc = ~crc;
    }
    return crc;
}

ConfigData read() {
    ConfigData data {0};
    EEPROM.begin(sizeof(ConfigData));
    EEPROM.get(0, data);
    EEPROM.end();
#ifdef DEBUG
    if (!isValid(data)) {
        PRINTLN("config::read(): data is not valid!");
    }
#endif
    return data;
}

bool write(ConfigData& data) {
    EEPROM.begin(sizeof(ConfigData));
    data.magic = magic;
    data.crc = GET_DATA_CRC(data);
    EEPROM.put(0, data);
    return EEPROM.end();
}

bool erase() {
    ConfigData data;
    return erase(data);
}

bool erase(ConfigData& data) {
    bzero(reinterpret_cast<uint8_t*>(&data), sizeof(data));
    data.magic = magic;
    EEPROM.begin(sizeof(data));
    EEPROM.put(0, data);
    return EEPROM.end();
}

bool isValid(ConfigData& data) {
    return data.crc == GET_DATA_CRC(data);
}

bool isDirty(ConfigData& data) {
    return data.magic != magic;
}

char* ConfigData::escapeNodeId(char* buf, size_t len) {
    if (len < 32)
        return nullptr;
    size_t id_len = strlen(node_id);
    char* c = node_id;
    char* dst = buf;
    for (size_t i = 0; i < id_len; i++) {
        if (*c == '"')
            *(dst++) = '\\';
        *(dst++) = *c;
        c++;
    }
    *dst = '\0';
    return buf;
}

}