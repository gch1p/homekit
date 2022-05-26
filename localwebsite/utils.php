#!/usr/bin/env php
<?php

require_once __DIR__.'/init.php';

function read_stdin(?string $prompt = null, bool $multiline = true) {
    if (!is_null($prompt))
        echo $prompt;

    if (!$multiline)
        return trim(fgets(STDIN));

    $fp = fopen('php://stdin', 'r');
    $data = stream_get_contents($fp);
    fclose($fp);

    return $data;
}

function usage() {
    global $argv;
    echo <<<EOF
usage: {$argv[0]} COMMAND

Supported commands:
    add-user
    change-password

EOF;
    exit(1);
}

if (empty($argv[1]))
    usage();

switch ($argv[1]) {
    case 'add-user':
        $username = read_stdin('enter username: ', false);
        $password = read_stdin('enter password: ', false);

        if (users::exists($username)) {
            fwrite(STDERR, "user already exists\n");
            exit(1);
        }

        $id = users::add($username, $password);
        echo "added user, id = $id\n";

        break;

    case 'change-password':
        $id = (int)read_stdin('enter ID: ', false);
        if (!$id)
            die("invalid id\n");

        $password = read_stdin('enter new password: ', false);
        if (!$password)
            die("invalid password\n");

        users::setPassword($id, $password);
        break;

    default:
        fwrite(STDERR, "invalid command\n");
        exit(1);
}