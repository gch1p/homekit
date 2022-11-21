<?php

class TemphumdClient extends MySimpleSocketClient {

    public string $name;
    public float $temp;
    public float $humidity;
    public ?int $flags;

    /**
     * @throws Exception
     */
    public function __construct(string $host, int $port, string $name, ?int $flags = null) {
        parent::__construct($host, $port);
        $this->name = $name;
        $this->flags = $flags;

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

    public function hasTemperature(): bool {
        return ($this->flags & config::TEMPHUMD_NO_TEMP) == 0;
    }

    public function hasHumidity(): bool {
        return ($this->flags & config::TEMPHUMD_NO_HUM) == 0;
    }

}