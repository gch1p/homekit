#!/usr/bin/env php
<?php

// this scripts pulls recent inbox from e3372 modem,
// looks for new messages from vk and re-sends them
// to the telegram group

require_once __DIR__.'/../init.php';
global $config;

$cfg = $config['modems'][$config['vk_sms_checker']['modem_name']];
$e3372 = new E3372($cfg['ip'], $cfg['legacy_token_auth']);

$db = getDB();

$last_processed = $db->querySingle("SELECT last_message_time FROM vk_processed");
$new_last_processed = 0;

$messages = $e3372->getSMSList();
$messages = array_reverse($messages);

$results = [];
if (!empty($messages)) {
    foreach ($messages as $m) {
        if ($m['timestamp'] <= $last_processed)
            continue;

        $new_last_processed = $m['timestamp'];
        if (preg_match('/^vk/i', $m['phone']) || preg_match('/vk/i', $m['content']))
            $results[] = $m;
    }
}

if (!empty($results)) {
    $t = new TelegramBotClient($config['vk_sms_checker']['telegram_token']);
    foreach ($results as $m) {
        $text = '<b>'.htmlescape($m['phone']).'</b> ('.$m['date'].')';
        $text .= "\n".htmlescape($m['content']);
        $t->sendMessage($config['vk_sms_checker']['telegram_chat_id'], $text);
    }
}

if ($new_last_processed != 0)
    $db->exec("UPDATE vk_processed SET last_message_time=?", $new_last_processed);