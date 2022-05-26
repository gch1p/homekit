<?php

class config {

    public static function get(string $key) {
        global $config;
        return is_callable($config[$key]) ? $config[$key]() : $config[$key];
    }

}