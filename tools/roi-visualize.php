#!/usr/bin/env php
<?php

function fatal(string $message) {
     fprintf(STDERR, $message);
     exit(1);
}

function parse_roi_input(string $file): array {
    if (!file_exists($file))
        throw new Error("file $file does not exists");

    $lines = file($file);
    $lines = array_map('trim', $lines);
    $lines = array_filter($lines, fn($line) => $line != '' && $line[0] != '#');
    $lines = array_map(fn($line) => array_map('intval', explode(' ', $line)), $lines);
    foreach ($lines as $points) {
        if (count($points) != 4)
            throw new Exception(__METHOD__.": invalid line: ".implode(' ', $points));
    }

    return $lines;
}

function hex2rgb(int $color): array {
    $r = ($color >> 16) & 0xff;
    $g = ($color >> 8) & 0xff;
    $b = $color & 0xff;
    return [$r, $g, $b];
}

function imageopen(string $filename) {
    $size = getimagesize($filename);
    $types = [
        2 => 'jpeg',
        3 => 'png'
    ];
    if (!$size || !isset($types[$size[2]]))
        return false;

    $f = 'imagecreatefrom'.$types[$size[2]];
    return call_user_func($f, $filename);
}

error_reporting(E_ALL);
ini_set('display_errors', 1);

$colors = [
    0xff0000,
    0x00ff00,
    0x0000ff,
    0xffff00,
    0xff00ff,
    0x00ffff,
];

if ($argc < 2)
    fatal("usage: {$argv[0]} --roi FILE --input PATH --output PATH\n");

try {
    array_shift($argv);
    while (count($argv) > 0) {
        switch ($argv[0]) {
            case '--roi':
                array_shift($argv);
                $roi_file = array_shift($argv);
                break;

            case '--input':
                array_shift($argv);
                $input = array_shift($argv);
                break;

            case '--output':
                array_shift($argv);
                $output = array_shift($argv);
                break;

            default:
                throw new Exception("unsupported argument: {$argv[0]}");
        }
    }

    if (!$roi_file)
        throw new Exception("--roi is not specified");

    if (!$input)
        throw new Exception('--input is not specified');

    if (!$output)
        throw new Exception('--output is not specified');

    $regions = parse_roi_input($roi_file);
    $img = imageopen($input);
    if (!$img)
        throw new Exception("failed to open image");

    $imgw = imagesx($img);
    $imgh = imagesy($img);

    foreach ($regions as $i => $region) {
        list($r, $g, $b) = hex2rgb($colors[$i]);

        if ($region[0]+$region[2] > $imgw || $region[1]+$region[3] > $imgh)
            throw new Exception('error: invalid region (line '.($i+1).')');

        $col = imagecolorallocatealpha($img, $r, $g, $b, 50);
        imagerectangle($img, $region[0], $region[1], $region[0]+$region[2], $region[1]+$region[3], $col);

        $col = imagecolorallocatealpha($img, $r, $g, $b, 90);
        imagefilledrectangle($img, $region[0]+1, $region[1]+1, $region[0]+$region[2]-2, $region[1]+$region[3]-2, $col);
    }

    imagejpeg($img, $output, 97);
    echo "saved to $output\n";
} catch (Exception $e) {
    fatal($e->getMessage()."\n");
}