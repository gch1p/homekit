<?php

class TelegramBotClient {

    protected string $token;

    public function __construct(string $token) {
        $this->token = $token;
    }

    public function sendMessage(int $chat_id, string $text): bool {
        $ch = curl_init();
        $url = 'https://api.telegram.org/bot'.$this->token.'/sendMessage';
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);
        curl_setopt($ch, CURLOPT_TIMEOUT, 10);
        curl_setopt($ch, CURLOPT_POSTFIELDS, [
            'chat_id' => $chat_id,
            'text' => $text,
            'parse_mode' => 'html',
            'disable_web_page_preview' => 1
        ]);
        $body = curl_exec($ch);
        curl_close($ch);

        $resp = jsonDecode($body);
        if (!$resp['ok']) {
            debugError(__METHOD__ . ': ' . $body);
            return false;
        }

        return true;
    }

}