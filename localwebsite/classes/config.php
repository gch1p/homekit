<?php

class config {

    const TEMPHUMD_NO_TEMP = 1 << 0;
    const TEMPHUMD_NO_HUM = 1 << 1;

    public static function get(string $key) {
        global $config;
        return is_callable($config[$key]) ? $config[$key]() : $config[$key];
    }

}