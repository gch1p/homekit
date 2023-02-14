<?php

class MiscHandler extends RequestHandler
{

    public function GET_main() {
        global $config;
        $this->tpl->set_title('Главная');
        $this->tpl->set([
            'grafana_sensors_url' => $config['grafana_sensors_url'],
            'grafana_inverter_url' => $config['grafana_inverter_url'],
            'cameras' => $config['cam_list']['labels']
        ]);
        $this->tpl->render_page('index.twig');
    }

    public function GET_sensors_page() {
        global $config;

        $clients = [];
        foreach ($config['temphumd_servers'] as $key => $params) {
            $cl = new TemphumdClient(...$params);
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

        list($hls_debug, $video_events, $high, $camera_ids) = $this->input('b:hls_debug, b:video_events, b:high, id');
        if ($camera_ids != '') {
            $camera_param = $camera_ids;
            $camera_ids = explode(',', $camera_ids);
            $camera_ids = array_filter($camera_ids);
            $camera_ids = array_map('trim', $camera_ids);
            $camera_ids = array_map('intval', $camera_ids);
        } else {
            $camera_ids = array_keys($config['cam_list']['labels']);
            $camera_param = '';
        }

        $tab = $high ? 'high' : 'low';

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

        $hls_key = config::get('cam_hls_access_key');
        if ($hls_key)
            setcookie_safe('hls_key', $hls_key);

        $cam_filter = function($id) use ($config, $camera_ids) {
            return in_array($id, $camera_ids);
        };

        $this->tpl->set([
            'hls_host' => $hls_host,
            'hls_proto' => $hls_proto,
            'hls_opts' => $hls_opts,
            'hls_access_key' => $config['cam_hls_access_key'],

            'camera_param' => $camera_param,
            'cams' => array_values(array_filter($config['cam_list'][$tab], $cam_filter)),
            'tab' => $tab,
            'video_events' => $video_events
        ]);
        $this->tpl->set_title('Камеры');
        $this->tpl->render_page('cams.twig');
    }

    public function GET_cams_stat() {
        global $config;
        list($ip, $port) = explode(':', $config['ipcam_server_api_addr']);
        $body = jsonDecode(file_get_contents('http://'.$ip.':'.$port.'/api/timestamp/all'));

        header('Content-Type: text/plain');
        $date_fmt = 'd.m.Y H:i:s';

        foreach ($body['response'] as $cam => $data) {
            $fix = date($date_fmt, $data['fix']);
            $start = date($date_fmt, $data['motion_start']);
            $motion = date($date_fmt, $data['motion']);
            echo "$cam:\n          motion: $motion\n";
            echo "    motion_start: $start\n";
            echo "             fix: $fix\n\n";
        }
    }

    public function GET_debug() {
        print_r($_SERVER);
    }

    public function GET_phpinfo() {
        phpinfo();
    }

}