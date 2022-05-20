<?php

class ModemHandler extends RequestHandler
{

    public function __construct()
    {
        parent::__construct();
        $this->tpl->add_static('modem.js');
    }

    public function GET_status_page() {
        global $config;

        $this->tpl->set([
            'modems' => $config['modems'],
            'js_modems' => array_keys($config['modems']),
        ]);

        $this->tpl->set_title('Состояние модемов');
        $this->tpl->render_page('modem_status_page.twig');
    }

    public function GET_status_get_ajax() {
        global $config;
        list($id) = $this->input('id');
        if (!isset($config['modems'][$id]))
            ajax_error('invalid modem id: '.$id);

        $modem_data = self::getModemData(
            $config['modems'][$id]['ip'],
            $config['modems'][$id]['legacy_token_auth']);

        ajax_ok([
            'html' => $this->tpl->render('modem_data.twig', [
                'loading' => false,
                'modem_data' => $modem_data
            ])
        ]);
    }


    public function GET_routing_smallhome_page() {
        global $config;

        list($error) = $this->input('error');
        $upstream = self::getCurrentSmallHomeUpstream();

        $current_upstream = [
            'key' => $upstream,
            'label' => $config['modems'][$upstream]['label']
        ];

        $this->tpl->set([
            'error' => $error,
            'current' => $current_upstream,
            'modems' => $config['modems'],
        ]);
        $this->tpl->set_title('Маршрутизация');
        $this->tpl->render_page('routing_page.twig');
    }

    public function GET_routing_smallhome_switch() {
        global $config;
        list($new_upstream) = $this->input('upstream');
        if (!isset($config['modems'][$new_upstream]))
            redirect('/routing/?error='.urlencode('invalid upstream'));

        $current_upstream = self::getCurrentSmallHomeUpstream();
        if ($current_upstream != $new_upstream) {
            if ($current_upstream != $config['routing_default'])
                MyOpenWrtUtils::ipsetDel($current_upstream, $config['routing_smallhome_ip']);
            if ($new_upstream != $config['routing_default'])
                MyOpenWrtUtils::ipsetAdd($new_upstream, $config['routing_smallhome_ip']);
        }

        redirect('/routing/');
    }

    public function GET_routing_ipsets_page() {
        list($error) = $this->input('error');

        $ip_sets = MyOpenWrtUtils::ipsetListAll();
        $this->tpl->set([
            'sets' => $ip_sets,
            'error' => $error
        ]);
        $this->tpl->set_title('Маршрутизация: IP sets');
        $this->tpl->render_page('routing_ipsets_page.twig');
    }

    public function GET_routing_ipsets_del() {
        list($set, $ip) = $this->input('set, ip');
        self::validateIpsetsInput($set, $ip);

        $output = MyOpenWrtUtils::ipsetDel($set, $ip);

        $url = '/routing/ipsets/';
        if ($output != '')
            $url .= '?error='.urlencode($output);
        redirect($url);
    }

    public function POST_routing_ipsets_add() {
        list($set, $ip) = $this->input('set, ip');
        self::validateIpsetsInput($set, $ip);

        $output = MyOpenWrtUtils::ipsetAdd($set, $ip);

        $url = '/routing/ipsets/';
        if ($output != '')
            $url .= '?error='.urlencode($output);
        redirect($url);
    }

    public function GET_routing_dhcp_page() {
        $leases = MyOpenWrtUtils::getDHCPLeases();
        $this->tpl->set([
            'leases' => $leases
        ]);
        $this->tpl->set_title('Маршрутизация: DHCP');
        $this->tpl->render_page('routing_dhcp_page.twig');
    }

    public function GET_sms_page() {
        global $config;

        list($selected) = $this->input('modem');
        if (!$selected)
            $selected = array_key_first($config['modems']);

        $cfg = $config['modems'][$selected];
        $e3372 = new E3372($cfg['ip'], $cfg['legacy_token_auth']);
        $messages = $e3372->getSMSList();

        $this->tpl->set([
            'modems_list' => array_keys($config['modems']),
            'modems' => $config['modems'],
            'selected_modem' => $selected,
            'messages' => $messages
         ]);
        $this->tpl->set_title('Модемы: SMS-сообщения');
        $this->tpl->render_page('sms_page.twig');
    }

    protected static function getModemData(string $ip, bool $need_auth = true): array {
        $modem = new E3372($ip, $need_auth);
        $signal = $modem->getDeviceSignal();
        $status = $modem->getMonitoringStatus();
        $traffic = $modem->getTrafficStats();
        return [
            'type' => e3372::getNetworkTypeLabel($status['CurrentNetworkType']),
            'level' => $status['SignalIcon'] ?? 0,
            'rssi' => $signal['rssi'],
            'sinr' => $signal['sinr'],
            'connected_time' => secondsToTime($traffic['CurrentConnectTime']),
            'downloaded' => bytesToUnitsLabel(gmp_init($traffic['CurrentDownload'])),
            'uploaded' => bytesToUnitsLabel(gmp_init($traffic['CurrentUpload'])),
        ];
    }

    protected static function getCurrentSmallHomeUpstream() {
        global $config;

        $upstream = null;
        $ip_sets = MyOpenWrtUtils::ipsetListAll();
        foreach ($ip_sets as $set => $ips) {
            if (in_array($config['routing_smallhome_ip'], $ips)) {
                $upstream = $set;
                break;
            }
        }
        if (is_null($upstream))
            $upstream = $config['routing_default'];

        return $upstream;
    }

    protected static function validateIpsetsInput($set, $ip) {
        global $config;

        if (!isset($config['modems'][$set]))
            redirect('/routing/ipsets/?error='.urlencode('invalid set: '.$set));

        if (($slashpos = strpos($ip, '/')) !== false)
            $ip = substr($ip, 0, $slashpos);

        if (!filter_var($ip, FILTER_VALIDATE_IP))
            redirect('/routing/ipsets/?error='.urlencode('invalid ip/network: '.$ip));
    }

}