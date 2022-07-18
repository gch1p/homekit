<?php

class E3372
{

    const WIFI_CONNECTING = '900';
    const WIFI_CONNECTED = '901';
    const WIFI_DISCONNECTED = '902';
    const WIFI_DISCONNECTING = '903';

    const CRADLE_CONNECTING = '900';
    const CRADLE_CONNECTED = '901';
    const CRADLE_DISCONNECTED = '902';
    const CRADLE_DISCONNECTING = '903';
    const CRADLE_CONNECTFAILED = '904';
    const CRADLE_CONNECTSTATUSNULL = '905';
    const CRANDLE_CONNECTSTATUSERRO = '906';

    const MACRO_EVDO_LEVEL_ZERO = '0';
    const MACRO_EVDO_LEVEL_ONE = '1';
    const MACRO_EVDO_LEVEL_TWO = '2';
    const MACRO_EVDO_LEVEL_THREE = '3';
    const MACRO_EVDO_LEVEL_FOUR = '4';
    const MACRO_EVDO_LEVEL_FIVE = '5';

    // CurrentNetworkType
    const MACRO_NET_WORK_TYPE_NOSERVICE = 0;
    const MACRO_NET_WORK_TYPE_GSM = 1;
    const MACRO_NET_WORK_TYPE_GPRS = 2;
    const MACRO_NET_WORK_TYPE_EDGE = 3;
    const MACRO_NET_WORK_TYPE_WCDMA = 4;
    const MACRO_NET_WORK_TYPE_HSDPA = 5;
    const MACRO_NET_WORK_TYPE_HSUPA = 6;
    const MACRO_NET_WORK_TYPE_HSPA = 7;
    const MACRO_NET_WORK_TYPE_TDSCDMA = 8;
    const MACRO_NET_WORK_TYPE_HSPA_PLUS = 9;
    const MACRO_NET_WORK_TYPE_EVDO_REV_0 = 10;
    const MACRO_NET_WORK_TYPE_EVDO_REV_A = 11;
    const MACRO_NET_WORK_TYPE_EVDO_REV_B = 12;
    const MACRO_NET_WORK_TYPE_1xRTT = 13;
    const MACRO_NET_WORK_TYPE_UMB = 14;
    const MACRO_NET_WORK_TYPE_1xEVDV = 15;
    const MACRO_NET_WORK_TYPE_3xRTT = 16;
    const MACRO_NET_WORK_TYPE_HSPA_PLUS_64QAM = 17;
    const MACRO_NET_WORK_TYPE_HSPA_PLUS_MIMO = 18;
    const MACRO_NET_WORK_TYPE_LTE = 19;
    const MACRO_NET_WORK_TYPE_EX_NOSERVICE = 0;
    const MACRO_NET_WORK_TYPE_EX_GSM = 1;
    const MACRO_NET_WORK_TYPE_EX_GPRS = 2;
    const MACRO_NET_WORK_TYPE_EX_EDGE = 3;
    const MACRO_NET_WORK_TYPE_EX_IS95A = 21;
    const MACRO_NET_WORK_TYPE_EX_IS95B = 22;
    const MACRO_NET_WORK_TYPE_EX_CDMA_1x = 23;
    const MACRO_NET_WORK_TYPE_EX_EVDO_REV_0 = 24;
    const MACRO_NET_WORK_TYPE_EX_EVDO_REV_A = 25;
    const MACRO_NET_WORK_TYPE_EX_EVDO_REV_B = 26;
    const MACRO_NET_WORK_TYPE_EX_HYBRID_CDMA_1x = 27;
    const MACRO_NET_WORK_TYPE_EX_HYBRID_EVDO_REV_0 = 28;
    const MACRO_NET_WORK_TYPE_EX_HYBRID_EVDO_REV_A = 29;
    const MACRO_NET_WORK_TYPE_EX_HYBRID_EVDO_REV_B = 30;
    const MACRO_NET_WORK_TYPE_EX_EHRPD_REL_0 = 31;
    const MACRO_NET_WORK_TYPE_EX_EHRPD_REL_A = 32;
    const MACRO_NET_WORK_TYPE_EX_EHRPD_REL_B = 33;
    const MACRO_NET_WORK_TYPE_EX_HYBRID_EHRPD_REL_0 = 34;
    const MACRO_NET_WORK_TYPE_EX_HYBRID_EHRPD_REL_A = 35;
    const MACRO_NET_WORK_TYPE_EX_HYBRID_EHRPD_REL_B = 36;
    const MACRO_NET_WORK_TYPE_EX_WCDMA = 41;
    const MACRO_NET_WORK_TYPE_EX_HSDPA = 42;
    const MACRO_NET_WORK_TYPE_EX_HSUPA = 43;
    const MACRO_NET_WORK_TYPE_EX_HSPA = 44;
    const MACRO_NET_WORK_TYPE_EX_HSPA_PLUS = 45;
    const MACRO_NET_WORK_TYPE_EX_DC_HSPA_PLUS = 46;
    const MACRO_NET_WORK_TYPE_EX_TD_SCDMA = 61;
    const MACRO_NET_WORK_TYPE_EX_TD_HSDPA = 62;
    const MACRO_NET_WORK_TYPE_EX_TD_HSUPA = 63;
    const MACRO_NET_WORK_TYPE_EX_TD_HSPA = 64;
    const MACRO_NET_WORK_TYPE_EX_TD_HSPA_PLUS = 65;
    const MACRO_NET_WORK_TYPE_EX_802_16E = 81;
    const MACRO_NET_WORK_TYPE_EX_LTE = 101;


    const ERROR_SYSTEM_NO_SUPPORT = 100002;
    const ERROR_SYSTEM_NO_RIGHTS = 100003;
    const ERROR_SYSTEM_BUSY = 100004;
    const ERROR_LOGIN_USERNAME_WRONG = 108001;
    const ERROR_LOGIN_PASSWORD_WRONG = 108002;
    const ERROR_LOGIN_ALREADY_LOGIN = 108003;
    const ERROR_LOGIN_USERNAME_PWD_WRONG = 108006;
    const ERROR_LOGIN_USERNAME_PWD_ORERRUN = 108007;
    const ERROR_LOGIN_TOUCH_ALREADY_LOGIN = 108009;
    const ERROR_VOICE_BUSY = 120001;
    const ERROR_WRONG_TOKEN = 125001;
    const ERROR_WRONG_SESSION = 125002;
    const ERROR_WRONG_SESSION_TOKEN = 125003;


    private $host;
    private $headers = [];
    private $authorized = false;
    private $useLegacyTokenAuth = false;

    public function __construct(string $host, bool $legacy_token_auth = false) {
        $this->host = $host;
        $this->useLegacyTokenAuth = $legacy_token_auth;
    }

    public function auth() {
        if ($this->authorized)
            return;

        if (!$this->useLegacyTokenAuth) {
            $data = $this->request('webserver/SesTokInfo');
            $this->headers = [
                'Cookie: '.$data['SesInfo'],
                '__RequestVerificationToken: '.$data['TokInfo'],
                'Content-Type: text/xml'
            ];
        } else {
            $data = $this->request('webserver/token');
            $this->headers = [
                '__RequestVerificationToken: '.$data['token'],
                'Content-Type: text/xml'
            ];
        }
        $this->authorized = true;
    }

    public function getDeviceInformation() {
        $this->auth();
        return $this->request('device/information');
    }

    public function getDeviceSignal() {
        $this->auth();
        return $this->request('device/signal');
    }

    public function getMonitoringStatus() {
        $this->auth();
        return $this->request('monitoring/status');
    }

    public function getNotifications() {
        $this->auth();
        return $this->request('monitoring/check-notifications');
    }

    public function getDialupConnection() {
        $this->auth();
        return $this->request('dialup/connection');
    }

    public function getTrafficStats() {
        $this->auth();
        return $this->request('monitoring/traffic-statistics');
    }

    public function getSMSCount() {
        $this->auth();
        return $this->request('sms/sms-count');
    }

    public function sendSMS(string $phone, string $text) {
        $this->auth();
        return $this->request('sms/send-sms', 'POST', [
            'Index' => -1,
            'Phones' => [
                'Phone' => $phone
            ],
            'Sca' => '',
            'Content' => $text,
            'Length' => -1,
            'Reserved' => 1,
            'Date' => -1
        ]);
    }

    public function getSMSList(int $page = 1, int $count = 20, bool $outbox = false) {
        $this->auth();
        $xml = $this->request('sms/sms-list', 'POST', [
            'PageIndex' => $page,
            'ReadCount' => $count,
            'BoxType' => !$outbox ? 1 : 2,
            'SortType' => 0,
            'Ascending' => 0,
            'UnreadPreferred' => !$outbox ? 1 : 0
        ], true);
        $xml = simplexml_load_string($xml);

        $messages = [];
        foreach ($xml->Messages->Message as $message) {
            $dt = DateTime::createFromFormat("Y-m-d H:i:s", (string)$message->Date);
            $messages[] = [
                'date' => (string)$message->Date,
                'timestamp' => $dt->getTimestamp(),
                'phone' => (string)$message->Phone,
                'content' => (string)$message->Content
            ];
        }
        return $messages;
    }

    private function xmlToAssoc(string $xml): array {
        $xml = new SimpleXMLElement($xml);
        $data = [];
        foreach ($xml as $name => $value) {
            $data[$name] = (string)$value;
        }
        return $data;
    }

    private function request(string $method, string $http_method = 'GET', array $data = [], bool $return_body = false) {
        $ch = curl_init();
        $url = 'http://'.$this->host.'/api/'.$method;
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        if (!empty($this->headers))
            curl_setopt($ch, CURLOPT_HTTPHEADER, $this->headers);
        if ($http_method == 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);

            $post_data = $this->postDataToXML($data);
            // debugLog('post_data:', $post_data);

            if (!empty($data))
                curl_setopt($ch, CURLOPT_POSTFIELDS, $post_data);
        }
        $body = curl_exec($ch);

        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if ($code != 200)
            throw new Exception('e3372 host returned code '.$code);

        curl_close($ch);
        return $return_body ? $body : $this->xmlToAssoc($body);
    }

    private function postDataToXML(array $data, int $depth = 1): string {
        if ($depth == 1)
            return '<?xml version: "1.0" encoding="UTF-8"?>'.$this->postDataToXML(['request' => $data], $depth+1);

        $items = [];
        foreach ($data as $key => $value) {
            if (is_array($value))
                $value = $this->postDataToXML($value, $depth+1);
            $items[] = "<{$key}>{$value}</{$key}>";
        }

        return implode('', $items);
    }

    public static function getNetworkTypeLabel($type): string {
        switch ((int)$type) {
            case self::MACRO_NET_WORK_TYPE_NOSERVICE: return 'NOSERVICE';
            case self::MACRO_NET_WORK_TYPE_GSM: return 'GSM';
            case self::MACRO_NET_WORK_TYPE_GPRS: return 'GPRS';
            case self::MACRO_NET_WORK_TYPE_EDGE: return 'EDGE';
            case self::MACRO_NET_WORK_TYPE_WCDMA: return 'WCDMA';
            case self::MACRO_NET_WORK_TYPE_HSDPA: return 'HSDPA';
            case self::MACRO_NET_WORK_TYPE_HSUPA: return 'HSUPA';
            case self::MACRO_NET_WORK_TYPE_HSPA: return 'HSPA';
            case self::MACRO_NET_WORK_TYPE_TDSCDMA: return 'TDSCDMA';
            case self::MACRO_NET_WORK_TYPE_HSPA_PLUS: return 'HSPA_PLUS';
            case self::MACRO_NET_WORK_TYPE_EVDO_REV_0: return 'EVDO_REV_0';
            case self::MACRO_NET_WORK_TYPE_EVDO_REV_A: return 'EVDO_REV_A';
            case self::MACRO_NET_WORK_TYPE_EVDO_REV_B: return 'EVDO_REV_B';
            case self::MACRO_NET_WORK_TYPE_1xRTT: return '1xRTT';
            case self::MACRO_NET_WORK_TYPE_UMB: return 'UMB';
            case self::MACRO_NET_WORK_TYPE_1xEVDV: return '1xEVDV';
            case self::MACRO_NET_WORK_TYPE_3xRTT: return '3xRTT';
            case self::MACRO_NET_WORK_TYPE_HSPA_PLUS_64QAM: return 'HSPA_PLUS_64QAM';
            case self::MACRO_NET_WORK_TYPE_HSPA_PLUS_MIMO: return 'HSPA_PLUS_MIMO';
            case self::MACRO_NET_WORK_TYPE_LTE: return 'LTE';
            case self::MACRO_NET_WORK_TYPE_EX_NOSERVICE: return 'NOSERVICE';
            case self::MACRO_NET_WORK_TYPE_EX_GSM: return 'GSM';
            case self::MACRO_NET_WORK_TYPE_EX_GPRS: return 'GPRS';
            case self::MACRO_NET_WORK_TYPE_EX_EDGE: return 'EDGE';
            case self::MACRO_NET_WORK_TYPE_EX_IS95A: return 'IS95A';
            case self::MACRO_NET_WORK_TYPE_EX_IS95B: return 'IS95B';
            case self::MACRO_NET_WORK_TYPE_EX_CDMA_1x: return 'CDMA_1x';
            case self::MACRO_NET_WORK_TYPE_EX_EVDO_REV_0: return 'EVDO_REV_0';
            case self::MACRO_NET_WORK_TYPE_EX_EVDO_REV_A: return 'EVDO_REV_A';
            case self::MACRO_NET_WORK_TYPE_EX_EVDO_REV_B: return 'EVDO_REV_B';
            case self::MACRO_NET_WORK_TYPE_EX_HYBRID_CDMA_1x: return 'HYBRID_CDMA_1x';
            case self::MACRO_NET_WORK_TYPE_EX_HYBRID_EVDO_REV_0: return 'HYBRID_EVDO_REV_0';
            case self::MACRO_NET_WORK_TYPE_EX_HYBRID_EVDO_REV_A: return 'HYBRID_EVDO_REV_A';
            case self::MACRO_NET_WORK_TYPE_EX_HYBRID_EVDO_REV_B: return 'HYBRID_EVDO_REV_B';
            case self::MACRO_NET_WORK_TYPE_EX_EHRPD_REL_0: return 'EHRPD_REL_0';
            case self::MACRO_NET_WORK_TYPE_EX_EHRPD_REL_A: return 'EHRPD_REL_A';
            case self::MACRO_NET_WORK_TYPE_EX_EHRPD_REL_B: return 'EHRPD_REL_B';
            case self::MACRO_NET_WORK_TYPE_EX_HYBRID_EHRPD_REL_0: return 'HYBRID_EHRPD_REL_0';
            case self::MACRO_NET_WORK_TYPE_EX_HYBRID_EHRPD_REL_A: return 'HYBRID_EHRPD_REL_A';
            case self::MACRO_NET_WORK_TYPE_EX_HYBRID_EHRPD_REL_B: return 'HYBRID_EHRPD_REL_B';
            case self::MACRO_NET_WORK_TYPE_EX_WCDMA: return 'WCDMA';
            case self::MACRO_NET_WORK_TYPE_EX_HSDPA: return 'HSDPA';
            case self::MACRO_NET_WORK_TYPE_EX_HSUPA: return 'HSUPA';
            case self::MACRO_NET_WORK_TYPE_EX_HSPA: return 'HSPA';
            case self::MACRO_NET_WORK_TYPE_EX_HSPA_PLUS: return 'HSPA_PLUS';
            case self::MACRO_NET_WORK_TYPE_EX_DC_HSPA_PLUS: return 'DC_HSPA_PLUS';
            case self::MACRO_NET_WORK_TYPE_EX_TD_SCDMA: return 'TD_SCDMA';
            case self::MACRO_NET_WORK_TYPE_EX_TD_HSDPA: return 'TD_HSDPA';
            case self::MACRO_NET_WORK_TYPE_EX_TD_HSUPA: return 'TD_HSUPA';
            case self::MACRO_NET_WORK_TYPE_EX_TD_HSPA: return 'TD_HSPA';
            case self::MACRO_NET_WORK_TYPE_EX_TD_HSPA_PLUS: return 'TD_HSPA_PLUS';
            case self::MACRO_NET_WORK_TYPE_EX_802_16E: return '802_16E';
            case self::MACRO_NET_WORK_TYPE_EX_LTE: return 'LTE';
            default: return '?';
        }
    }

}
