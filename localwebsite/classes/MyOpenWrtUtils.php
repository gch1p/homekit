<?php

class MyOpenWrtUtils {

    public static function getRoutingTable($table = null) {
        $arguments = ['route-show'];
        if ($table)
            $arguments[] = $table;

        return self::toList(self::run($arguments));
    }

    public static function getRoutingRules() {
        return self::toList(self::run(['rule-show']));
    }

    public static function ipsetList($set_name) {
        return self::toList(self::run(['ipset-list', $set_name]));
    }

    public static function ipsetListAll() {
        global $config;

        $args = ['ipset-list-all'];
        $args = array_merge($args, array_keys($config['modems']));

        $lines = self::toList(self::run($args));

        $sets = [];
        $cur_set = null;
        foreach ($lines as $line) {
            if (startsWith($line, '>')) {
                $cur_set = substr($line, 1);
                if (!isset($sets[$cur_set]))
                    $sets[$cur_set] = [];
                continue;
            }

            if (is_null($cur_set)) {
                debugError(__METHOD__.': cur_set is not set');
                continue;
            }

            $sets[$cur_set][] = $line;
        }

        return $sets;
    }

    public static function ipsetAdd($set_name, $ip) {
        return self::run(['ipset-add', $set_name, $ip]);
    }

    public static function ipsetDel($set_name, $ip) {
        return self::run(['ipset-del', $set_name, $ip]);
    }

    public static function getDHCPLeases() {
        $list = self::toList(self::run(['dhcp-leases']));
        $list = array_map('self::toDHCPLease', $list);
        return $list;
    }


    //
    // http functions
    //

    private static function run(array $arguments) {
        $url = self::getLink($arguments);

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        $body = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if ($code != 200)
            throw new Exception(__METHOD__.': http code '.$code);

        curl_close($ch);
        return trim($body);
    }

    private static function getLink($arguments) {
        global $config;

        $url = 'http://'.$config['openwrt_ip'].'/cgi-bin/luci/command/cfg099944';
        if (!empty($arguments)) {
            $arguments = array_map(function($arg) {
                $arg = str_replace('/', '_', $arg);
                return urlencode($arg);
            }, $arguments);
            $arguments = implode('%20', $arguments);

            $url .= '/';
            $url .= $arguments;
        }

        // debugLog($url);

        return $url;
    }


    //
    // parsing functions
    //

    private static function toList(string $s): array {
        if ($s == '')
            return [];
        return explode("\n", $s);
    }

    private static function toDHCPLease(string $s): array {
        $words = explode(' ', $s);
        $time = array_shift($words);
        $mac = array_shift($words);
        $ip = array_shift($words);
        array_pop($words);
        $hostname = trim(implode(' ', $words));
        if (!$hostname || $hostname == '*')
            $hostname = '?';
        return [
            'time' => $time,
            'time_s' => date('d M, H:i:s', $time),
            'mac' => $mac,
            'ip' => $ip,
            'hostname' => $hostname
        ];
    }

}