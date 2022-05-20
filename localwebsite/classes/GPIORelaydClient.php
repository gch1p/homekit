<?php

class GPIORelaydClient extends MySimpleSocketClient {

    const STATUS_ON = 'on';
    const STATUS_OFF = 'off';

    public function setStatus(string $status) {
        $this->send($status);
        return $this->recv();
    }

    public function getStatus() {
        $this->send('get');
        return $this->recv();
    }

}