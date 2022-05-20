<?php

class InverterdClient extends MySimpleSocketClient {

    /**
     * @throws Exception
     */
    public function setProtocol(int $v): string
    {
        $this->send("v $v");
        return $this->recv();
    }

    /**
     * @throws Exception
     */
    public function setFormat(string $fmt): string
    {
        $this->send("format $fmt");
        return $this->recv();
    }

    /**
     * @throws Exception
     */
    public function exec(string $command, array $arguments = []): string
    {
        $buf = "exec $command";
        if (!empty($arguments)) {
            foreach ($arguments as $arg)
                $buf .= " $arg";
        }
        $this->send($buf);
        return $this->recv();
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
            if (endsWith($buf, "\r\n\r\n"))
                break;
        }

        $response = explode("\r\n", $buf);
        $status = array_shift($response);
        if (!in_array($status, ['ok', 'err']))
            throw new Exception(__METHOD__.': unexpected status ('.$status.')');
        if ($status == 'err')
            throw new Exception(empty($response) ? 'unknown inverterd error' : $response[0]);

        return trim(implode("\r\n", $response));
    }

}