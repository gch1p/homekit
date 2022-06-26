# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
import logging
import socket
import random
import struct
import threading
import queue

from enum import Enum
from typing import Union, Optional, Any
from ipaddress import IPv4Address, IPv6Address

import cryptography.hazmat.primitives._serialization

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import ciphers, padding, hashes
from cryptography.hazmat.primitives.ciphers import algorithms, modes


_logger = logging.getLogger(__name__)


# drop-in replacement for Java API
# TODO: rewrite
def arraycopy(src, src_pos, dest, dest_pos, length):
    for i in range(length):
        dest[i + dest_pos] = src[i + src_pos]


class FrameType(Enum):
    ACK = 0
    CMD = 1
    AUX = 2
    NAK = 3


class PowerType(Enum):
    OFF = 0  # turn off
    ON = 1  # turn on, set target temperature to 100
    CUSTOM = 3  # turn on, allows custom target temperature
    # MYSTERY_MODE = 2  # don't know what 2 means, needs testing
    # update: if I set it to '2', it just resets to '0'


class FrameHead:
    seq: int  # u8
    type: FrameType  # u8
    length: int  # u16

    @staticmethod
    def from_bytes(buf: bytes) -> FrameHead:
        seq, ft, length = struct.unpack('<BBH', buf)
        return FrameHead(seq, FrameType(ft), length)

    def __init__(self, seq: int, frame_type: FrameType, length: Optional[int] = None):
        self.seq = seq
        self.type = frame_type
        self.length = length or 0

    def pack(self) -> bytes:
        assert self.length != 0, "FrameHead.length has not been set"
        return struct.pack('<BBH', self.seq, self.type.value, self.length)


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
    def from_encrypted(buf: bytes,
                       inkey: bytes,
                       outkey: bytes) -> Message:
        # _logger.debug('[from_encrypted] buf='+buf.hex())
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

        key = bytearray(len(inkey))
        arraycopy(inkey, j, key, 0, len(inkey) - j)
        arraycopy(inkey, 0, key, len(inkey) - j, j)

        iv = bytearray(len(outkey))
        arraycopy(outkey, k, iv, 0, len(outkey) - k)
        arraycopy(outkey, 0, iv, len(outkey) - k, k)

        cipher = ciphers.Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(payload) + decryptor.finalize()

        # print(f'head.length={head.length} len(decr)={len(decrypted_data)}')
        # if len(decrypted_data) > head.length:
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        decrypted_data = unpadder.update(decrypted_data)
        # try:
        decrypted_data += unpadder.finalize()
        # except ValueError as exc:
        #     _logger.exception(exc)
        #     pass

        assert len(decrypted_data) != 0, 'decrypted data is null'
        assert head.seq == decrypted_data[0], f'decrypted seq mismatch {head.seq} != {decrypted_data[0]}'

        # _logger.debug('Message.from_encrypted: plaintext: '+decrypted_data.hex())

        if head.type == FrameType.ACK:
            return AckMessage(head.seq)

        elif head.type == FrameType.NAK:
            return NakMessage(head.seq)

        elif head.type == FrameType.AUX:
            raise NotImplementedError('FrameType AUX is not yet implemented')

        elif head.type == FrameType.CMD:
            cmd = decrypted_data[0]
            data = decrypted_data[2:]
            return CmdMessage(head.seq, cmd, data)

        else:
            raise NotImplementedError(f'Unexpected frame type: {head.type}')

    @property
    def data(self) -> bytes:
        return b''

    def encrypt(self,
                outkey: bytes,
                inkey: bytes,
                token: bytes,
                pubkey: bytes):

        assert self.frame is not None

        data = self.data
        assert data is not None

        b = self.frame.head.seq
        i = b & 0xf
        j = b >> 4 & 0xf

        outkey = bytearray(outkey)

        l = len(outkey)
        key = bytearray(l)

        arraycopy(outkey, i, key, 0, l-i)
        arraycopy(outkey, 0, key, l-i, i)

        inkey = bytearray(inkey)

        l = len(inkey)
        iv = bytearray(l)

        arraycopy(inkey, j, iv, 0, l-j)
        arraycopy(inkey, 0, iv, l-j, j)

        cipher = ciphers.Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()

        newdata = bytearray(len(data)+1)
        newdata[0] = b

        arraycopy(data, 0, newdata, 1, len(data))

        newdata = bytes(newdata)
        _logger.debug('payload to be sent: ' + newdata.hex())

        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        ciphertext = bytearray()
        ciphertext.extend(encryptor.update(padder.update(newdata) + padder.finalize()))
        ciphertext.extend(encryptor.finalize())

        self.frame.setpayload(ciphertext)

    def set_seq(self, seq: int):
        self.frame.head.seq = seq

    def __repr__(self):
        return f'<{self.__class__.__name__} seq={self.frame.head.seq}>'


class AckMessage(Message):
    def __init__(self, seq: int = 0):
        super().__init__()
        self.frame = FrameItem(FrameHead(seq, FrameType.ACK, 0))


class NakMessage(Message):
    def __init__(self, seq: int = 0):
        super().__init__()
        self.frame = FrameItem(FrameHead(seq, FrameType.NAK, 0))


class CmdMessage(Message):
    _type: Optional[int]
    _data: bytes

    def __init__(self, seq=0,
                 type: Optional[int] = None,
                 data: bytes = b''):
        super().__init__()
        self._data = data
        if type is not None:
            self.frame = FrameItem(FrameHead(seq, FrameType.CMD))
            self._type = type
        else:
            self._type = None

    @property
    def data(self) -> bytes:
        buf = bytearray()
        buf.append(self._type)
        buf.extend(self._data)
        return bytes(buf)

    def __repr__(self):
        params = [
            __name__+'.'+self.__class__.__name__,
            f'seq={self.frame.head.seq}',
            # f'type={self.frame.head.type}',
            f'cmd={self._type}'
        ]
        if self._data:
            params.append(f'data={self._data.hex()}')
        return '<'+' '.join(params)+'>'


class ModeMessage(CmdMessage):
    def __init__(self, power_type: PowerType):
        super().__init__(type=1,
                         data=(power_type.value).to_bytes(1, byteorder='little'))


class TargetTemperatureMessage(CmdMessage):
    def __init__(self, temp: int):
        super().__init__(type=2,
                         data=bytes(bytearray([temp, 0])))


class HandshakeMessage(CmdMessage):
    def __init__(self):
        super().__init__(type=0)

    def encrypt(self,
                outkey: bytes,
                inkey: bytes,
                token: bytes,
                pubkey: bytes):
        cipher = ciphers.Cipher(algorithms.AES(outkey), modes.CBC(inkey))
        encryptor = cipher.encryptor()

        ciphertext = bytearray()
        ciphertext.extend(encryptor.update(token))
        ciphertext.extend(encryptor.finalize())

        pld = bytearray()
        pld.append(0)
        pld.extend(pubkey)
        pld.extend(ciphertext)

        self.frame.setpayload(pld)


# TODO
# implement resending UDP messages if no answer has been received in a second
# try at least 5 times, then give up
class Connection(threading.Thread):
    seq_no: int
    source_port: int
    device_addr: str
    device_port: int
    device_token: bytes
    interrupted: bool
    waiting_for_response: dict[int, callable]
    pubkey: Optional[bytes]
    encinkey: Optional[bytes]
    encoutkey: Optional[bytes]

    def __init__(self,
                 addr: Union[IPv4Address, IPv6Address],
                 port: int,
                 device_pubkey: bytes,
                 device_token: bytes):
        super().__init__()
        self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)
        self.setName(self.__class__.__name__)
        # self.daemon = True

        self.seq_no = -1
        self.source_port = random.randint(1024, 65535)
        self.device_addr = str(addr)
        self.device_port = port
        self.device_token = device_token
        self.lock = threading.Lock()
        self.outgoing_queue = queue.SimpleQueue()
        self.waiting_for_response = {}
        self.interrupted = False

        self.pubkey = None
        self.encinkey = None
        self.encoutkey = None

        self.prepare_keys(device_pubkey)

    def prepare_keys(self, device_pubkey: bytes):
        # generate key pair
        privkey = X25519PrivateKey.generate()

        self.pubkey = bytes(reversed(privkey.public_key().public_bytes(encoding=cryptography.hazmat.primitives._serialization.Encoding.Raw,
                                                                       format=cryptography.hazmat.primitives._serialization.PublicFormat.Raw)))

        # generate shared key
        device_pubkey = X25519PublicKey.from_public_bytes(
            bytes(reversed(device_pubkey))
        )
        shared_key = bytes(reversed(
            privkey.exchange(device_pubkey)
        ))

        # in/out encryption keys
        digest = hashes.Hash(hashes.SHA256())
        digest.update(shared_key)

        shared_sha256 = digest.finalize()

        self.encinkey = shared_sha256[:16]
        self.encoutkey = shared_sha256[16:]

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', self.source_port))
        sock.settimeout(1)

        while not self.interrupted:
            if not self.outgoing_queue.empty():
                message = self.outgoing_queue.get()
                message.encrypt(outkey=self.encoutkey,
                                inkey=self.encinkey,
                                token=self.device_token,
                                pubkey=self.pubkey)
                buf = message.frame.pack()
                self.logger.debug('send: '+buf.hex())
                self.logger.debug(f'sendto: {self.device_addr}:{self.device_port}')
                sock.sendto(buf, (self.device_addr, self.device_port))
            try:
                data = sock.recv(4096)
                self.handle_incoming(data)
            except TimeoutError:
                pass

    def handle_incoming(self, buf: bytes):
        self.logger.debug('handle_incoming: '+buf.hex())
        message = Message.from_encrypted(buf, inkey=self.encinkey, outkey=self.encoutkey)
        if message.frame.head.seq in self.waiting_for_response:
            self.logger.info(f'received awaited message: {message}')
            try:
                f = self.waiting_for_response[message.frame.head.seq]
                f(message)
            except Exception as exc:
                self.logger.exception(exc)
            finally:
                del self.waiting_for_response[message.frame.head.seq]
        else:
            self.logger.info(f'received message (not awaited): {message}')

    def send_message(self, message: Message, callback: callable):
        seq = self.next_seqno()
        message.set_seq(seq)
        self.outgoing_queue.put(message)
        self.waiting_for_response[seq] = callback

    def next_seqno(self) -> int:
        with self.lock:
            self.seq_no += 1
            self.logger.debug(f'next_seqno: set to {self.seq_no}')
        return self.seq_no
