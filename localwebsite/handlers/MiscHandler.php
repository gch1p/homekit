<?php

class MiscHandler extends RequestHandler
{

    public function GET_main() {
        $this->tpl->set_title('Главная');
        $this->tpl->render_page('index.twig');
    }

    public function GET_phpinfo() {
        phpinfo();
        exit;
    }

    public function GET_sensors_page() {
        global $config;

        $clients = [];
        foreach ($config['si7021d_servers'] as $key => $params) {
            $cl = new Si7021dClient(...$params);
            $clients[$key] = $cl;

            $cl->readSensor();
        }

        $this->tpl->set(['sensors' => $clients]);
        $this->tpl->set_title('Датчики');
        $this->tpl->render_page('sensors.twig');
    }

    public function GET_pump_page() {
        global $config;

        list($set) = $this->input('set');
        $client = new GPIORelaydClient($config['pump_host'], $config['pump_port']);

        if ($set == GPIORelaydClient::STATUS_ON || $set == GPIORelaydClient::STATUS_OFF) {
            $client->setStatus($set);
            redirect('/pump/');
        }

        $status = $client->getStatus();

        $this->tpl->set([
            'status' => $status
        ]);
        $this->tpl->set_title('Насос');
        $this->tpl->render_page('pump.twig');
    }

}