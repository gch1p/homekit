import socket


class RelayClient:
    def __init__(self, port=8307, host='127.0.0.1'):
        self._host = host
        self._port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __del__(self):
        self.sock.close()

    def connect(self):
        self.sock.connect((self._host, self._port))

    def _write(self, line):
        self.sock.sendall((line+'\r\n').encode())

    def _read(self):
        buf = bytearray()
        while True:
            buf.extend(self.sock.recv(256))
            if b'\r\n' in buf:
                break

        response = buf.decode().strip()
        return response

    def on(self):
        self._write('on')
        return self._read()

    def off(self):
        self._write('off')
        return self._read()

    def status(self):
        self._write('get')
        return self._read()
