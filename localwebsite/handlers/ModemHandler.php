<?php

use libphonenumber\NumberParseException;
use libphonenumber\PhoneNumberFormat;
use libphonenumber\PhoneNumberUtil;

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
                'modem' => $id,
                'modem_data' => $modem_data
            ])
        ]);
    }

    public function GET_verbose_page() {
        global $config;

        list($modem) = $this->input('modem');
        if (!$modem)
            $modem = array_key_first($config['modems']);

        list($signal, $status, $traffic, $device, $dialup_conn) = self::getModemData(
            $config['modems'][$modem]['ip'],
            $config['modems'][$modem]['legacy_token_auth'],
            true);

        $data = [
            ['Signal', $signal],
            ['Connection', $status],
            ['Traffic', $traffic],
            ['Device info', $device],
            ['Dialup connection', $dialup_conn]
        ];
        $this->tpl->set([
            'data' => $data,
            'modem_name' => $config['modems'][$modem]['label'],
        ]);
        $this->tpl->set_title('Подробная информация о модеме '.$modem);
        $this->tpl->render_page('modem_verbose_page.twig');
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
        $overrides = config::get('dhcp_hostname_overrides');
        $leases = MyOpenWrtUtils::getDHCPLeases();
        foreach ($leases as &$lease) {
            if ($lease['hostname'] == '?' && array_key_exists($lease['mac'], $overrides))
                $lease['hostname'] = $overrides[$lease['mac']];
        }
        $this->tpl->set([
            'leases' => $leases
        ]);
        $this->tpl->set_title('Маршрутизация: DHCP');
        $this->tpl->render_page('routing_dhcp_page.twig');
    }

    public function GET_sms() {
        global $config;

        list($selected, $is_outbox, $error, $sent) = $this->input('modem, b:outbox, error, b:sent');
        if (!$selected)
            $selected = array_key_first($config['modems']);

        $cfg = $config['modems'][$selected];
        $e3372 = new E3372($cfg['ip'], $cfg['legacy_token_auth']);
        $messages = $e3372->getSMSList(1, 20, $is_outbox);

        $this->tpl->set([
            'modems_list' => array_keys($config['modems']),
            'modems' => $config['modems'],
            'selected_modem' => $selected,
            'messages' => $messages,
            'is_outbox' => $is_outbox,
            'error' => $error,
            'is_sent' => $sent
        ]);

        $direction = $is_outbox ? 'исходящие' : 'входящие';
        $this->tpl->set_title('SMS-сообщения ('.$direction.', '.$selected.')');
        $this->tpl->render_page('sms_page.twig');
    }

    public function POST_sms() {
        global $config;

        list($selected, $is_outbox, $phone, $text) = $this->input('modem, b:outbox, phone, text');
        if (!$selected)
            $selected = array_key_first($config['modems']);

        $return_url = '/sms/?modem='.$selected;
        if ($is_outbox)
            $return_url .= '&outbox=1';

        $go_back = function(?string $error = null) use ($return_url) {
            if (!is_null($error))
                $return_url .= '&error='.urlencode($error);
            else
                $return_url .= '&sent=1';
            redirect($return_url);
        };

        $phone = preg_replace('/\s+/', '', $phone);

        // при отправке смс на короткие номера не надо использовать libphonenumber и вот это вот всё
        if (strlen($phone) > 4) {
            $country = null;
            if (!startsWith($phone, '+'))
                $country = 'RU';

            $phoneUtil = PhoneNumberUtil::getInstance();
            try {
                $number = $phoneUtil->parse($phone, $country);
            } catch (NumberParseException $e) {
                debugError(__METHOD__.': failed to parse number '.$phone.': '.$e->getMessage());
                $go_back('Неверный номер ('.$e->getMessage().')');
                return;
            }

            if (!$phoneUtil->isValidNumber($number)) {
                $go_back('Неверный номер');
                return;
            }

            $phone = $phoneUtil->format($number, PhoneNumberFormat::E164);
        }

        $cfg = $config['modems'][$selected];
        $e3372 = new E3372($cfg['ip'], $cfg['legacy_token_auth']);

        $result = $e3372->sendSMS($phone, $text);
        debugLog($result);

        $go_back();
    }

    protected static function getModemData(string $ip,
                                           bool $need_auth = true,
                                           bool $get_raw_data = false): array {
        $modem = new E3372($ip, $need_auth);

        $signal = $modem->getDeviceSignal();
        $status = $modem->getMonitoringStatus();
        $traffic = $modem->getTrafficStats();

        if ($get_raw_data) {
            $device_info = $modem->getDeviceInformation();
            $dialup_conn = $modem->getDialupConnection();
            return [$signal, $status, $traffic, $device_info, $dialup_conn];
        } else {
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