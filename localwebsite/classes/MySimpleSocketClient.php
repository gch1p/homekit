<?php

class MySimpleSocketClient {

    protected $sock;

    public function __construct(string $host, int $port)
    {
        if (($socket = socket_create(AF_INET, SOCK_STREAM, SOL_TCP)) === false)
            throw new Exception("socket_create() failed: ".$this->getSocketError());
        
        $this->sock = $socket;

        if ((socket_connect($socket, $host, $port)) === false)
            throw new Exception("socket_connect() failed: ".$this->getSocketError());
    }

    public function __destruct()
    {
        $this->close();
    }

    /**
     * @throws Exception
     */
    public function send(string $data)
    {
        $data .= "\r\n";
        $remained = strlen($data);

        while ($remained > 0) {
            $result = socket_write($this->sock, $data);
            if ($result === false)
                throw new Exception(__METHOD__ . ": socket_write() failed: ".$this->getSocketError());

            $remained -= $result;
            if ($remained > 0)
                $data = substr($data, $result);
        }
    }

    /**
     * @throws Exception
     */
    public function recv()
    {
        $recv_buf = '';
        $buf = '';

        while (true) {
            $result = socket_recv($this->sock, $recv_buf, 1024, 0);
            if ($result === false)
                throw new Exception(__METHOD__ . ": socket_recv() failed: " . $this->getSocketError());

            // peer disconnected
            if ($result === 0)
                break;

            $buf .= $recv_buf;
            if (endsWith($buf, "\r\n"))
                break;
        }

        return trim($buf);
    }

    /**
     * Close connection.
     */
    public function close()
    {
        if (!$this->sock)
            return;

        socket_close($this->sock);
        $this->sock = null;
    }

    /**
     * @return string
     */
    protected function getSocketError(): string
    {
        $sle_args = [];
        if ($this->sock !== null)
            $sle_args[] = $this->sock;
        return socket_strerror(socket_last_error(...$sle_args));
    }

}