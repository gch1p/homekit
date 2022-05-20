<?php

class Si7021dClient extends MySimpleSocketClient {

    public string $name;
    public float $temp;
    public float $humidity;

    /**
     * @throws Exception
     */
    public function __construct(string $host, int $port, string $name) {
        parent::__construct($host, $port);
        $this->name = $name;

        socket_set_timeout($this->sock, 3);
    }

    public function readSensor(): void {
        $this->send('read');

        $data = jsonDecode($this->recv());

        $temp = round((float)$data['temp'], 3);
        $hum = round((float)$data['humidity'], 3);

        $this->temp = $temp;
        $this->humidity = $hum;
    }

}