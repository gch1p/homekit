<?php

return [
    'group' => 'www-data',
    'files_mode' => 0664,
    'dirs_mode' => 0775,
    'is_dev' => true,
    'static_public_path' => '/assets',

    'openwrt_ip' => '192.168.1.1',

    'inverterd_host' => '192.168.1.2',
    'inverterd_port' => 8305,

    'pump_host' => '192.168.1.2',
    'pump_port' => 8307,

    'temphumd_servers' => [
        // fill here, example:
        'hall' => ['192.168.1.3', 8306, 'Big Hall'/*, optional: config::TEMPHUMD_NO_HUM */],
    ],

    // modem names (array keys) must match ipset names and
    // routing table names on the openwrt router
    //
    // the order of the keys in the array must be the same
    // as the order in which fwmark iptables rules are applied
    'modems' => [
        'modem-example' => [
            'ip' => '1.2.3.4',
            'label' => 'Modem Name',
            'short_label' => 'Mname',
            'legacy_token_auth' => false,
        ],
    ],

    // 'routing_smallhome_ip' => 'fill_me',
    // 'routing_default' => 'fill_me',

    'debug_backtrace' => true,
    'debug_file' => '.debug.log',

    'twig_cache' => true,
    'templates' => [
        'web' => [
            'root' => 'templates-web',
            'cache' => 'cache/templates-web',
        ],
    ],

    'static' => [
        'app.css' => 10,
        'app.js' => 5,
        'polyfills.js' => 1,
        'modem.js' => 2,
        'inverter.js' => 2,
    ],

    'cam_hls_access_key' => '',
    'cam_hls_proto' => 'http', // bool|callable
    'cam_hls_host' => '192.168.1.1', // bool|callable
    'cam_list' => [
        'low' => [
            // fill me with names
        ],
        'high' => [
            // fill me with names
        ],
    ],

    'vk_sms_checker' => [
        'telegram_token' => '',
        'telegram_chat_id' => '',
        'modem_name' => '', // reference to the 'modems' array
    ],

    'database_path' => getenv('HOME').'/.config/homekit.localwebsite.sqlite3',

    'auth_cookie_host' => '',
    'auth_need' => false, // bool|callable
    'auth_pw_salt' => '',

    'grafana_sensors_url' => '',
    'grafana_inverter_url' => '',

    'dhcp_hostname_overrides' => [],
];
