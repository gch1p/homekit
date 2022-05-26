<?php

function param($key) {
    global $RouterInput;

    $val = null;

    if (isset($RouterInput[$key])) {
        $val = $RouterInput[$key];
    } else if (isset($_POST[$key])) {
        $val = $_POST[$key];
    } else if (isset($_GET[$key])) {
        $val = $_GET[$key];
    }

    if (is_array($val)) {
        $val = implode($val);
    }
    return $val;
}

function str_replace_once(string $needle, string $replace, string $haystack): string {
    $pos = strpos($haystack, $needle);
    if ($pos !== false) {
        $haystack = substr_replace($haystack, $replace, $pos, strlen($needle));
    }
    return $haystack;
}

function htmlescape($s) {
    if (is_array($s)) {
        foreach ($s as $k => $v) {
            $s[$k] = htmlescape($v);
        }
        return $s;
    }
    return htmlspecialchars($s, ENT_QUOTES, 'UTF-8');
}

function jsonEncode($obj) {
    return json_encode($obj, JSON_UNESCAPED_UNICODE);
}

function jsonDecode($json) {
    return json_decode($json, true);
}

function startsWith(string $haystack, string $needle): bool {
    return $needle === "" || strpos($haystack, $needle) === 0;
}

function endsWith(string $haystack, string $needle): bool {
    return $needle === "" || substr($haystack, -strlen($needle)) === $needle;
}

function exectime($format = null) {
    $time = round(microtime(true) - START_TIME, 4);
    if (!is_null($format)) {
        $time = sprintf($format, $time);
    }
    return $time;
}

function stransi($s) {
    static $colors = [
        'black'   => 0,
        'red'     => 1,
        'green'   => 2,
        'yellow'  => 3,
        'blue'    => 4,
        'magenta' => 5,
        'cyan'    => 6,
        'white'   => 7
    ];
    static $valid_styles = ['bold', 'fgbright', 'bgbright'];

    $s = preg_replace_callback('/<(?:e ([a-z, =]+)|\/e)>/', function($match) use ($colors, $valid_styles) {
        if (empty($match[1])) {
            return "\033[0m";
        } else {
            $codes = [];
            $args = preg_split('/ +/', $match[1]);
            $fg = null;
            $bg = null;
            $styles = [];
            foreach ($args as $arg) {
                list($argname, $argvalue) = explode('=', $arg);
                $err = false;
                if ($argname == 'fg' || $argname == 'bg') {
                    if (isset($colors[$argvalue])) {
                        $$argname = $colors[$argvalue];
                    } else {
                        $err = true;
                    }
                } else if ($argname == 'style') {
                    $argstyles = array_filter(explode(',', $argvalue));
                    foreach ($argstyles as $style) {
                        if (!in_array($style, $valid_styles)) {
                            $err = true;
                            break;
                        }
                    }
                    if (!$err) {
                        foreach ($argstyles as $style) {
                            $styles[$style] = true;
                        }
                    }
                } else {
                    $err = true;
                }

                if ($err) {
                    trigger_error(__FUNCTION__.": unrecognized argument {$arg}", E_USER_WARNING);
                }
            }

            if (!is_null($fg)) {
                $codes[] = $fg + (isset($styles['fgbright']) ? 90 : 30);
            }
            if (!is_null($bg)) {
                $codes[] = $bg + (isset($styles['bgbright']) ? 100 : 40);
            }
            if (isset($styles['bold'])) {
                $codes[] = 1;
            }

            return !empty($codes) ? "\033[".implode(';', $codes)."m" : '';
        }
    }, $s);
    return $s;
}

function strgen($len = 10): string {
    $buf = '';
    for ($i = 0; $i < $len; $i++) {
        $j = mt_rand(0, 61);
        if ($j >= 36) {
            $j += 13;
        } else if ($j >= 10) {
            $j += 7;
        }
        $buf .= chr(48 + $j);
    }
    return $buf;
}

function setperm($file, $is_dir = null) {
    global $config;

    // chgrp
    $gid = filegroup($file);
    $gname = posix_getgrgid($gid);
    if (!is_array($gname)) {
        debugError(__FUNCTION__.": posix_getgrgid() failed on $gid", $gname);
    } else {
        $gname = $gname['name'];
    }
    if ($gname != $config['group']) {
        if (!chgrp($file, $config['group'])) {
            debugError(__FUNCTION__.": chgrp() failed on $file");
        }
    }

    // chmod
    $perms = fileperms($file);
    $need_perms = is_dir($file) ? $config['dirs_mode'] : $config['files_mode'];
    if (($perms & $need_perms) !== $need_perms) {
        if (!chmod($file, $need_perms)) {
            debugError(__FUNCTION__.": chmod() failed on $file");
        }
    }
}

function redirect($url, $preserve_utm = true, $no_ajax = false) {
    if (PHP_SAPI != 'cli' && $_SERVER['REQUEST_METHOD'] == 'GET' && $preserve_utm) {
        $proxy_params = ['utm_source', 'utm_medium', 'utm_content', 'utm_campaign'];
        $params = [];
        foreach ($proxy_params as $p) {
            if (!empty($_GET[$p])) {
                $params[$p] = (string)$_GET[$p];
            }
        }
        if (!empty($params)) {
            if (($anchor_pos = strpos($url, '#')) !== false) {
                $anchor = substr($url, $anchor_pos+1);
                $url = substr($url, 0, $anchor_pos);
            }
            $url .= (strpos($url, '?') === false ? '?' : '&').http_build_query($params);
            if ($anchor_pos !== false) {
                $url .= '#'.$anchor;
            }
        }
    }

    header('Location: ' . $url);
    exit;
}

function is_xhr_request(): bool {
    return isset($_SERVER['HTTP_X_REQUESTED_WITH']) && $_SERVER['HTTP_X_REQUESTED_WITH'] == 'XMLHttpRequest';
}

function secondsToTime(int $n): string {
    $parts = [];

    if ($n >= 86400) {
        $days = floor($n / 86400);
        $n %= 86400;
        $parts[] = "{$days}д";
    }

    if ($n >= 3600) {
        $hours = floor($n / 3600);
        $n %= 3600;
        $parts[] = "{$hours}ч";
    }

    if ($n >= 60) {
        $minutes = floor($n / 60);
        $n %= 60;
        $parts[] = "{$minutes}мин";
    }

    if ($n)
        $parts[] = "{$n}сек";

    return implode(' ', $parts);
}

function bytesToUnitsLabel(GMP $b): string {
    $ks = array('B', 'Kb', 'Mb', 'Gb', 'Tb');
    foreach ($ks as $i => $k) {
        if (gmp_cmp($b, gmp_pow(1024, $i + 1)) < 0) {
            if ($i == 0)
                return gmp_strval($b) . ' ' . $k;

            $n = gmp_intval(gmp_div_q($b, gmp_pow(1024, $i)));
            return round($n, 2).' '.$k;
        }
    }

    return gmp_strval($b);
}

function pwhash(string $s): string {
    return hash('sha256', config::get('auth_pw_salt').'|'.$s);
}

$ShutdownFunctions = [];

function append_shutdown_function(callable $f) {
    global $ShutdownFunctions;
    $ShutdownFunctions[] = $f;
}

function prepend_shutdown_function(callable $f) {
    global $ShutdownFunctions;
    array_unshift($ShutdownFunctions, $f);
}

function getDB(): database {
    static $link = null;

    if (is_null($link))
        $link = new database(config::get('database_path'));

    return $link;
}

function to_camel_case(string $input, string $separator = '_'): string {
    return lcfirst(str_replace($separator, '', ucwords($input, $separator)));
}

function from_camel_case(string $s): string {
    $buf = '';
    $len = strlen($s);
    for ($i = 0; $i < $len; $i++) {
        if (!ctype_upper($s[$i])) {
            $buf .= $s[$i];
        } else {
            $buf .= '_'.strtolower($s[$i]);
        }
    }
    return $buf;
}