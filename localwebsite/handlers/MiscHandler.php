<?php

class MiscHandler extends RequestHandler
{

    public function GET_main() {
        $this->tpl->set_title('Главная');
        $this->tpl->render_page('index.twig');
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

    public function GET_cams() {
        global $config;

        list($hls_debug, $video_events) = $this->input('b:hls_debug, b:video_events');

        $hls_opts = [
            'startPosition' => -1,

            // // https://github.com/video-dev/hls.js/issues/3884#issuecomment-842380784
            'liveSyncDuration' => 2,
            'liveMaxLatencyDuration' => 3,
            'maxLiveSyncPlaybackRate' => 2,
            'liveDurationInfinity' => true,
        ];

        if ($hls_debug)
            $hls_opts['debug'] = true;

        $this->tpl->add_external_static('js', 'https://cdn.jsdelivr.net/npm/hls.js@latest');

        $hls_host = config::get('cam_hls_host');
        $hls_proto = config::get('cam_hls_proto');

        $this->tpl->set([
            'hls_host' => $hls_host,
            'hls_proto' => $hls_proto,
            'hls_opts' => $hls_opts,
            'hls_access_key' => $config['cam_hls_access_key'],

            'cams' => $config['cam_list'],
            'video_events' => $video_events
        ]);
        $this->tpl->set_title('Камеры');
        $this->tpl->render_page('cams.twig');
    }

    public function GET_debug() {
        print_r($_SERVER);
    }

    public function GET_phpinfo() {
        phpinfo();
    }

}