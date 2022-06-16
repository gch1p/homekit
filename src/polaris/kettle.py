from __future__ import annotations

import logging
import zeroconf
import socket
import random
import struct

from enum import Enum
from ipaddress import ip_address, IPv4Address, IPv6Address
from typing import Union, Optional, Any

import cryptography
import cryptography.hazmat.primitives._serialization
from cryptography.hazmat.primitives.asymmetric.ec import SECP192R1, SECP256R1, SECP384R1
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import hashes, ciphers, padding
from cryptography.hazmat.primitives.ciphers import algorithms, modes

_logger = logging.getLogger(__name__)
PubkeyType = Union[Any, X25519PublicKey, bytes]
PrivkeyType = Union[Any, X25519PrivateKey, bytes]


# com.syncleoiot.iottransport.utils.crypto.EllipticCurveCoder
class CurveType(Enum):
    secp192r1 = 19
    secp256r1 = 23
    secp384r1 = 24
    x25519 = 29


def key_to_bytes(key: Union[str, bytes, X25519PrivateKey, X25519PublicKey], reverse=False) -> bytes:
    val = None

    if isinstance(key, str):
        val = bytes.fromhex(key)

    if isinstance(key, bytes):
        # logger.warning('key_to_bytes: key is bytes already')
        val = key

    raw_kwargs = dict(encoding=cryptography.hazmat.primitives._serialization.Encoding.Raw,
                      format=cryptography.hazmat.primitives._serialization.PublicFormat.Raw)

    if isinstance(key, X25519PublicKey):
        val = key.public_bytes(**raw_kwargs)

    elif isinstance(key, X25519PrivateKey):
        val = key.private_bytes(**raw_kwargs)

    assert type(val) is bytes

    if reverse:
        val = bytes(reversed(val))

    return val


def key_to_hex(key: Union[str, bytes, X25519PrivateKey, X25519PublicKey]) -> str:
    return key_to_bytes(key).hex()


def arraycopy(src, src_pos, dest, dest_pos, length):
    for i in range(length):
        dest[i + dest_pos] = src[i + src_pos]


def pack(fmt, *args):
    # enforce little endian
    return struct.pack(f'<{fmt}', *args)


def unpack(fmt, *args):
    # enforce little endian
    return struct.unpack(f'<{fmt}', *args)


class FrameType(Enum):
    ACK = 0
    CMD = 1
    AUX = 2
    NAK = 3


class FrameHead:
    seq: int  # u8
    type: FrameType  # u8
    length: int  # u16

    @staticmethod
    def from_bytes(buf: bytes) -> FrameHead:
        seq, ft, length = unpack('BBH', buf)
        return FrameHead(seq, FrameType(ft), length)

    def __init__(self, seq: int, frame_type: FrameType, length: Optional[int] = None):
        self.seq = seq
        self.type = frame_type
        self.length = length or 0

    def pack(self) -> bytes:
        assert self.length != 0, "FrameHead.length has not been set"
        return pack('BBH', self.seq, self.type.value, self.length)


class FrameItem:
    head: FrameHead
    payload: bytes

    def __init__(self, head: FrameHead, payload: Optional[bytes] = None):
        self.head = head
        self.payload = payload

    def setpayload(self, payload: Union[bytes, bytearray]):
        if isinstance(payload, bytearray):
            payload = bytes(payload)
        self.payload = payload
        self.head.length = len(payload)

    def pack(self) -> bytes:
        ba = bytearray(self.head.pack())
        ba.extend(self.payload)
        return bytes(ba)


class Message:
    frame: Optional[FrameItem]

    def __init__(self):
        self.frame = None

    @staticmethod
    def from_encrypted(buf: bytes, inkey: bytes, outkey: bytes) -> Message:
        _logger.debug('[from_encrypted] buf='+buf.hex())
        # print(f'buf len={len(buf)}')
        assert len(buf) >= 4, 'invalid size'
        head = FrameHead.from_bytes(buf[:4])

        assert len(buf) == head.length + 4, f'invalid buf size ({len(buf)} != {head.length})'

        payload = buf[4:]

        # byte b = paramFrameHead.seq;
        b = head.seq

        # TODO check if protocol is 2, otherwise raise an exception

        j = b & 0xF
        k = b >> 4 & 0xF

        # arrayOfByte1 = this.encryptionInKey;
        key = bytearray(len(inkey))
        arraycopy(inkey, j, key, 0, len(inkey) - j)
        arraycopy(inkey, 0, key, len(inkey) - j, j)

        # arrayOfByte1 = this.encryptionOutKey;
        iv = bytearray(len(outkey))
        arraycopy(outkey, k, iv, 0, len(outkey) - k)
        arraycopy(outkey, 0, iv, len(outkey) - k, k)

        cipher = ciphers.Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(payload) + decryptor.finalize()

        # print(f'head.length={head.length} len(decr)={len(decrypted_data)}')
        if len(decrypted_data) > head.length:
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            decrypted_data = unpadder.update(decrypted_data)
            try:
                decrypted_data += unpadder.finalize()
            except ValueError as exc:
                _logger.exception(exc)
                pass

        _logger.debug('decrypted data:', decrypted_data.hex())

        assert len(decrypted_data) != 0, 'decrypted data is null'
        assert head.seq == decrypted_data[0], f'decrypted seq mismatch {head.seq} != {decrypted_data[0]}'

        if head.type == FrameType.ACK:
            return AckMessage(head.seq)

        elif head.type == FrameType.NAK:
            return NakMessage(head.seq)

        else:
            cmd = decrypted_data[0]
            data = decrypted_data[2:]
            return CmdMessage(head.seq, cmd, data)

    def encrypt(self):
        raise RuntimeError('this method is abstract')

    @property
    def data(self) -> bytes:
        raise RuntimeError('this method is abstract')

    def _encrypt(self,
                 outkey: bytes,
                 inkey: bytes,
                 token: bytes,
                 pubkey: bytes):

        assert self.frame is not None

        data = self.data
        assert data is not None

        # print('data: '+data.hex())

        b = self.frame.head.seq
        i = b & 0xf
        j = b >> 4 & 0xf

        # byte[] arrayOfByte1 = this.encryptionOutKey;
        outkey = bytearray(outkey)

        # arrayOfByte = new byte[arrayOfByte1.length];
        l = len(outkey)
        key = bytearray(l)

        # System.arraycopy(arrayOfByte1, i, arrayOfByte, 0, arrayOfByte1.length - i);
        arraycopy(outkey, i, key, 0, l-i)

        # arrayOfByte1 = this.encryptionOutKey;
        # System.arraycopy(arrayOfByte1, 0, arrayOfByte, arrayOfByte1.length - i, i);
        arraycopy(outkey, 0, key, l-i, i)

        # byte[] arrayOfByte2 = this.encryptionInKey;
        inkey = bytearray(inkey)

        # arrayOfByte1 = new byte[arrayOfByte2.length];
        l = len(inkey)
        iv = bytearray(l)

        # System.arraycopy(arrayOfByte2, j, arrayOfByte1, 0, arrayOfByte2.length - j);
        arraycopy(inkey, j, iv, 0, l-j)
        # arrayOfByte2 = this.encryptionInKey;
        # System.arraycopy(arrayOfByte2, 0, arrayOfByte1, arrayOfByte2.length - j, j);
        arraycopy(inkey, 0, iv, l-j, j)

        # Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        # SecretKeySpec secretKeySpec = new SecretKeySpec();
        # this(arrayOfByte, "AES");
        # IvParameterSpec ivParameterSpec = new IvParameterSpec();
        # this(arrayOfByte1);
        # cipher.init(1, secretKeySpec, ivParameterSpec);

        cipher = ciphers.Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()

        # arrayOfByte = new byte[paramArrayOfbyte.length + 1];
        # arrayOfByte[0] = b;
        # System.arraycopy(paramArrayOfbyte, 0, arrayOfByte, 1, paramArrayOfbyte.length);
        # data = bytearray(data)

        newdata = bytearray(len(data)+1)
        newdata[0] = b

        # data = bytearray(len(payload)+1)
        # data[0] = b
        arraycopy(data, 0, newdata, 1, len(data))

        newdata = bytes(newdata)
        _logger.debug('payload to be sent:' + newdata.hex())

        # arrayOfByte = ByteUtils.concatArrays(cipher.update(arrayOfByte), cipher.doFinal());
        encdata = bytearray()
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        encdata.extend(encryptor.update(padder.update(newdata) + padder.finalize()))
        encdata.extend(encryptor.finalize())

        self.frame.setpayload(encdata)

    def construct(self) -> FrameItem:
        raise RuntimeError('this is an abstract method')


class AckMessage(Message):
    def __init__(self, seq: int):
        super().__init__()
        self.frame = FrameItem(FrameHead(seq, FrameType.ACK, 0))


class NakMessage(Message):
    def __init__(self, seq: int):
        super().__init__()
        self.frame = FrameItem(FrameHead(seq, FrameType.NAK, 0))


class CmdMessage(Message):
    cmd: Optional[int]
    cmd_data: Optional[Union[bytes, str]]

    def __init__(self,
                 seq: Optional[int] = None,
                 cmd: Optional[int] = None,
                 cmd_data: Optional[bytes] = None):
        super().__init__()

        if (seq is not None) and (cmd is not None) and (cmd_data is not None):
            self.frame = FrameItem(FrameHead(seq, FrameType.CMD))
            # self.frame.setpayload(data)
            self.cmd = cmd
            self.cmd_data = cmd_data
        else:
            self.cmd = None
            self.cmd_data = None

    @property
    def data(self) -> bytes:
        buf = bytearray()
        buf.append(self.cmd)
        buf.extend(self.cmd_data)
        # print(buf)
        return bytes(buf)


class ModeMessage(CmdMessage):
    def __init__(self, seq: int, on: bool):
        super().__init__(seq, 1, b'\x01' if on else b'\x00')


class TargetTemperatureMessage(CmdMessage):
    def __init__(self, seq: int, temp: int):
        super().__init__(seq, 2, bytes(bytearray([temp, 0])))


class HandshakeMessage(CmdMessage):
    def _encrypt(self,
                outkey: bytes,
                inkey: bytes,
                token: bytes,
                pubkey: bytes):
        cipher = ciphers.Cipher(algorithms.AES(outkey), modes.CBC(inkey))
        encryptor = cipher.encryptor()

        encr_data = bytearray()
        encr_data.extend(encryptor.update(token))
        encr_data.extend(encryptor.finalize())

        payload = bytearray()

        # const/4 v7, 0x0
        # aput-byte v7, v5, v7
        payload.append(0)

        payload.extend(pubkey)
        payload.extend(encr_data)

        self.frame = FrameItem(FrameHead(0, FrameType.CMD))
        self.frame.setpayload(payload)


# Polaris PWK 1725CGLD IoT kettle
class Kettle(zeroconf.ServiceListener):
    macaddr: str
    token: str
    sb: Optional[zeroconf.ServiceBrowser]
    found_device: Optional[zeroconf.ServiceInfo]
    privkey: Optional[Union[Any, X25519PrivateKey]]
    pubkey: Optional[bytes]
    sharedkey: Optional[bytes]
    sharedsha256: Optional[bytes]
    encinkey: Optional[bytes]
    encoutkey: Optional[bytes]
    seqno: int

    def __init__(self, mac: str, token: str):
        super().__init__()
        self.zeroconf = zeroconf.Zeroconf()
        self.sb = None
        self.macaddr = mac
        self.token = token
        self.found_device = None
        self.privkey = None
        self.pubkey = None
        self.sharedkey = None
        self.sharedsha256 = None
        self.encinkey = None
        self.encoutkey = None
        self.sourceport = random.randint(1024, 65535)
        self.seqno = 0

    def find(self):
        self.sb = zeroconf.ServiceBrowser(self.zeroconf, "_syncleo._udp.local.", self)
        self.sb.join()
        # return self.found_device

    # zeroconf.ServiceListener implementation
    def add_service(self,
                    zc: zeroconf.Zeroconf,
                    type_: str,
                    name: str) -> None:
        if name.startswith(f'{self.macaddr}.'):
            info = zc.get_service_info(type_, name)
            try:
                self.sb.cancel()
            except RuntimeError:
                pass
            self.zeroconf.close()
            self.found_device = info

    # def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
    #     print(f"Service {name} updated")
    #
    # def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
    #     print(f"Service {name} removed")

    @property
    def device_pubkey(self) -> str:
        return self.found_device.properties[b'public'].decode()

    @property
    def device_addresses(self) -> list[Union[IPv4Address, IPv6Address]]:
        return list(map(ip_address, self.found_device.addresses))

    @property
    def device_port(self) -> int:
        return int(self.found_device.port)

    # @property
    # def device_pubkey_bytes(self) -> bytes:
    #     return bytes.fromhex(self.device_pubkey)

    @property
    def curve_type(self) -> CurveType:
        return CurveType(int(self.found_device.properties[b'curve'].decode()))

    def genkeys(self):
        # based on decompiled EllipticCurveCoder.java

        if self.curve_type in (CurveType.secp192r1, CurveType.secp256r1, CurveType.secp384r1):
            if self.curve_type == CurveType.secp192r1:
                curve = SECP192R1()
            elif self.curve_type == CurveType.secp256r1:
                curve = SECP256R1()
            elif self.curve_type == CurveType.secp384r1:
                curve = SECP384R1()
            else:
                raise TypeError(f'unexpected curve type: {self.curve_type}')

            self.privkey = cryptography.hazmat.primitives.asymmetric.ec.generate_private_key(curve)

        elif self.curve_type == CurveType.x25519:
            self.privkey = X25519PrivateKey.generate()

        self.pubkey = key_to_bytes(self.privkey.public_key(), reverse=True)

    def genshared(self):
        self.sharedkey = bytes(reversed(
            self.privkey.exchange(X25519PublicKey.from_public_bytes(
                key_to_bytes(self.device_pubkey, reverse=True))
            )
        ))

        digest = hashes.Hash(hashes.SHA256())
        digest.update(self.sharedkey)
        self.sharedsha256 = digest.finalize()

        self.encinkey = self.sharedsha256[:16]
        self.encoutkey = self.sharedsha256[16:]

    def next_seqno(self) -> int:
        self.seqno += 1
        return self.seqno

    def setpower(self, on: bool):
        message = ModeMessage(self.next_seqno(), on)
        print(self.do_send(message))

    def settemperature(self, temp: int):
        message = TargetTemperatureMessage(self.next_seqno(), temp)
        print(self.do_send(message))

    def handshake(self):
        message = HandshakeMessage()
        response = self.do_send(message)
        assert response.frame.head.type == FrameType.ACK, 'ACK expected'

    def do_send(self, message: Message) -> Message:
        message._encrypt(pubkey=self.pubkey,
                         outkey=self.encoutkey,
                         inkey=self.encinkey,
                         token=bytes.fromhex(self.token))

        dst_addr = str(self.device_addresses[0])
        dst_port = self.device_port

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', self.sourceport))
        sock.sendto(message.frame.pack(), (dst_addr, dst_port))
        _logger.debug('data has been sent, waiting for incoming data....')

        data = sock.recv(4096)
        return Message.from_encrypted(data, inkey=self.encinkey, outkey=self.encoutkey)