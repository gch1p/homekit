<?php

// require_once 'engine/mysql.php';

class debug {

    protected static $Types = [
        1     => 'E_ERROR',
        2     => 'E_WARNING',
        4     => 'E_PARSE',
        8     => 'E_NOTICE',
        16    => 'E_CORE_ERROR',
        32    => 'E_CORE_WARNING',
        64    => 'E_COMPILE_ERROR',
        128   => 'E_COMPILE_WARNING',
        256   => 'E_USER_ERROR',
        512   => 'E_USER_WARNING',
        1024  => 'E_USER_NOTICE',
        2048  => 'E_STRICT',
        4096  => 'E_RECOVERABLE_ERROR',
        8192  => 'E_DEPRECATED',
        16384 => 'E_USER_DEPRECATED',
        32767 => 'E_ALL'
    ];

    const STORE_NONE = -1;
    const STORE_MYSQL = 0;
    const STORE_FILE  = 1;
    const STORE_BOTH  = 2;

    private static $instance = null;

    protected $enabled = false;
    protected $errCounter = 0;
    protected $logCounter = 0;
    protected $messagesStoreType = self::STORE_NONE;
    protected $errorsStoreType = self::STORE_NONE;
    protected $filter;
    protected $reportRecursionLevel = 0;
    protected $overridenDebugFile = null;
    protected $silent = false;
    protected $prefix;

    private function __construct($filter) {
        $this->filter = $filter;
    }

    public static function getInstance($filter = null) {
        if (is_null(self::$instance)) {
            self::$instance = new self($filter);
        }
        return self::$instance;
    }

    public function enable() {
        $self = $this;

        set_error_handler(function($no, $str, $file, $line) use ($self) {
            if ($self->silent || !$self->enabled) {
                return;
            }
            if ((is_callable($this->filter) && !($this->filter)($no, $file, $line, $str)) || !$self->canReport()) {
                return;
            }
            $self->report(true, $str, $no, $file, $line);
        });

        append_shutdown_function(function() use ($self) {
            if (!$self->enabled || !($error = error_get_last())) {
                return;
            }
            if (is_callable($this->filter)
                && !($this->filter)($error['type'], $error['file'], $error['line'], $error['message'])) {
                return;
            }
            if (!$self->canReport()) {
                return;
            }
            $self->report(true, $error['message'], $error['type'], $error['file'], $error['line']);
        });

        $this->enabled = true;
    }

    public function disable() {
        restore_error_handler();
        $this->enabled = false;
    }

    public function report($is_error, $text, $errno = 0, $errfile = '', $errline = '') {
        global $config;

        $this->reportRecursionLevel++;

        $logstarted = $this->errCounter > 0 || $this->logCounter > 0;
        $num = $is_error ? $this->errCounter++ : $this->logCounter++;
        $custom = $is_error && !$errno;
        $ts = time();
        $exectime = exectime();
        $bt = backtrace(2);

        $store_file = (!$is_error && $this->checkMessagesStoreType(self::STORE_FILE))
            || ($is_error && $this->checkErrorsStoreType(self::STORE_FILE));

        $store_mysql = (!$is_error && $this->checkMessagesStoreType(self::STORE_MYSQL))
            || ($is_error && $this->checkErrorsStoreType(self::STORE_MYSQL));

        if ($this->prefix)
            $text = $this->prefix.$text;

        // if ($store_mysql) {
        //     $db = getMySQL('local_logs', true);
        //     $data = [
        //         'ts' => $ts,
        //         'num' => $num,
        //         'time' => $exectime,
        //         'custom' => intval($custom),
        //         'errno' => $errno,
        //         'file' => $errfile,
        //         'line' => $errline,
        //         'text' => $text,
        //         'stacktrace' => $bt,
        //         'is_cli' => PHP_SAPI == 'cli' ? 1 : 0,
        //     ];
        //     if (PHP_SAPI == 'cli') {
        //         $data += [
        //             'ip' => '',
        //             'ua' => '',
        //             'url' => '',
        //         ];
        //     } else {
        //         $data += [
        //             'ip' => ip2ulong($_SERVER['REMOTE_ADDR']),
        //             'ua' => $_SERVER['HTTP_USER_AGENT'] ?? '',
        //             'url' => $_SERVER['HTTP_HOST'].$_SERVER['REQUEST_URI']
        //         ];
        //     }
        //     $db->insert('backend_errors', $data);
        // }

        if ($store_file) {
            $title = PHP_SAPI == 'cli' ? 'cli' : $_SERVER['REQUEST_URI'];
            $date = date('d/m/y H:i:s', $ts);
            $exectime = (string)$exectime;
            if (strlen($exectime) < 6)
                $exectime .= str_repeat('0', 6 - strlen($exectime));

            $buf = "";
            if (!$logstarted) {
                $buf .= "\n<e fg=white bg=magenta style=fgbright,bold> {$title} </e><e fg=white bg=blue style=fgbright> {$date} </e>\n";
            }
            $buf .= "<e fg=".($is_error ? 'red' : 'white').">".($is_error ? 'E' : 'I')."=<e style=bold>${num}</e> <e fg=cyan>{$exectime}</e> ";
            if ($is_error && !$custom) {
                $buf .= "<e fg=green>{$errfile}<e fg=white>:<e fg=green style=fgbright>{$errline}</e> (".self::errname($errno).") ";
            }
            $buf = stransi($buf);

            $buf .= $text;
            $buf .= "\n";
            if ($is_error && $config['debug_backtrace']) {
                $buf .= $bt."\n";
            }

            $debug_file = $this->getDebugFile();

            $logdir = dirname($debug_file);
            if (!file_exists($logdir)) {
                mkdir($logdir);
                setperm($logdir);
            }

            $f = fopen($debug_file, 'a');
            if ($f) {
                fwrite($f, $buf);
                fclose($f);
            }
        }

        $this->reportRecursionLevel--;
    }

    public function canReport() {
        return $this->reportRecursionLevel < 2;
    }

    public function setErrorsStoreType($errorsStoreType) {
        $this->errorsStoreType = $errorsStoreType;
    }

    public function setMessagesStoreType($messagesStoreType) {
        $this->messagesStoreType = $messagesStoreType;
    }

    public function checkMessagesStoreType($store_type) {
        return $this->messagesStoreType == $store_type || $this->messagesStoreType == self::STORE_BOTH;
    }

    public function checkErrorsStoreType($store_type) {
        return $this->errorsStoreType == $store_type || $this->errorsStoreType == self::STORE_BOTH;
    }

    public function overrideDebugFile($file) {
        $this->overridenDebugFile = $file;
    }

    protected function getDebugFile() {
        global $config;
        return is_null($this->overridenDebugFile) ? ROOT.'/'.$config['debug_file'] : $this->overridenDebugFile;
    }

    public function setSilence($silent) {
        $this->silent = $silent;
    }

    public function setPrefix($prefix) {
        $this->prefix = $prefix;
    }

    public static function errname($errno) {
        static $errors = null;
        if (is_null($errors)) {
            $errors = array_flip(array_slice(get_defined_constants(true)['Core'], 0, 15, true));
        }
        return $errors[$errno];
    }

    public static function getTypes() {
        return self::$Types;
    }

}

class debug_measure {

    private $name;
    private $time;
    private $started = false;

    /**
     * @param string $name
     * @return $this
     */
    public function start($name = null) {
        if (is_null($name)) {
            $name = strgen(3);
        }
        $this->name = $name;
        $this->time = microtime(true);
        $this->started = true;
        return $this;
    }

    /**
     * @return float|string|null
     */
    public function finish() {
        if (!$this->started) {
            debugLog("debug_measure::finish(): not started, name=".$this->name);
            return null;
        }

        $time = (microtime(true) - $this->time);
        debugLog("MEASURE".($this->name != '' ? ' '.$this->name : '').": ".$time);

        $this->started = false;
        return $time;
    }

}

/**
 * @param $var
 * @return string
 */
function str_print_r($var) {
    ob_start();
    print_r($var);
    return trim(ob_get_clean());
}

/**
 * @param $var
 * @return string
 */
function str_var_dump($var) {
    ob_start();
    var_dump($var);
    return trim(ob_get_clean());
}

/**
 * @param $args
 * @param bool $all_dump
 * @return string
 */
function str_vars($args, $all_dump = false) {
    return implode(' ', array_map(function($a) use ($all_dump) {
        if ($all_dump) {
            return str_var_dump($a);
        }
        $type = gettype($a);
        if ($type == 'string' || $type == 'integer' || $type == 'double') {
            return $a;
        } else if ($type == 'array' || $type == 'object') {
            return str_print_r($a);
        } else {
            return str_var_dump($a);
        }
    }, $args));
}

/**
 * @param int $shift
 * @return string
 */
function backtrace($shift = 0) {
    $bt = debug_backtrace();
    $lines = [];
    foreach ($bt as $i => $t) {
        if ($i < $shift) {
            continue;
        }
        if (!isset($t['file'])) {
            $lines[] = 'from ?';
        } else {
            $lines[] = 'from '.$t['file'].':'.$t['line'];
        }
    }
    return implode("\n", $lines);
}

/**
 * @param mixed ...$args
 */
function debugLog(...$args) {
    global $config;
    if (!$config['is_dev'])
        return;

    debug::getInstance()->report(false, str_vars($args));
}

function debugLogOnProd(...$args) {
    debug::getInstance()->report(false, str_vars($args));
}

/**
 * @param mixed ...$args
 */
function debugError(...$args) {
    $debug = debug::getInstance();
    if ($debug->canReport()) {
        $debug->report(true, str_vars($args));
    }
}
