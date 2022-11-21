<?php

error_reporting(E_ALL);
ini_set('display_errors', 1);

mb_internal_encoding('UTF-8');
mb_regex_encoding('UTF-8');

register_shutdown_function(function() {
    global $ShutdownFunctions;
    if (!empty($ShutdownFunctions)) {
        foreach ($ShutdownFunctions as $f)
            $f();
    }
});

spl_autoload_register(function($class) {
    if (endsWith($class, 'Handler'))
        $path = ROOT.'/handlers/'.$class.'.php';

    // engine classes
    else if (in_array($class, ['request_handler', 'router', 'model', 'debug', 'database']))
        $path = ROOT.'/engine/'.$class.'.php';

    else if ($class == 'Lang')
        $path = ROOT.'/engine/lang.php';

    else if (endsWith($class, '_tpl'))
        $path = ROOT.'/engine/tpl.php';

    // other classes
    else
        $path = ROOT.'/classes/'.$class.'.php';

    if (strpos($path, '\\') !== false)
        $path = str_replace('\\', '/', $path);

    if (is_file($path))
        require_once $path;
});

define('ROOT', __DIR__);
define('START_TIME', microtime(true));

set_include_path(get_include_path().PATH_SEPARATOR.ROOT);

require_once ROOT.'/functions.php';

$config = require ROOT.'/config.php';
if (!is_file(ROOT.'/config.local.php'))
    die('config.local.php not found');
$config = array_merge($config, require_once ROOT.'/config.local.php');

// it's better to start logging as early as possible
$debug = debug::getInstance(
    function($errno, $errfile, $errlne, $errstr) {
        // it's not our fault that some vendor package uses something that's deprecated
        // so let's not spam our logs
        if ($errno == E_USER_DEPRECATED && startsWith($errfile, ROOT.'/vendor/'))
            return false;

        return true;
    }
);
$debug->setMessagesStoreType(debug::STORE_FILE);
$debug->setErrorsStoreType(debug::STORE_FILE);
$debug->enable();
unset($debug);

// composer
require_once ROOT.'/vendor/autoload.php';
