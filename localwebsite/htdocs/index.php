<?php

require_once __DIR__.'/../init.php';

$router = new router;

// modem
$router->add('modem/status/',         'Modem status_page');
$router->add('modem/status/get.ajax', 'Modem status_get_ajax');

$router->add('routing/',                   'Modem routing_smallhome_page');
$router->add('routing/switch-small-home/', 'Modem routing_smallhome_switch');
$router->add('routing/{ipsets,dhcp}/',     'Modem routing_${1}_page');
$router->add('routing/ipsets/{add,del}/',  'Modem routing_ipsets_${1}');

$router->add('modem/sms/',     'Modem sms_page');
// $router->add('modem/set.ajax', 'Modem ctl_set_ajax');

// inverter
$router->add('inverter/',            'Inverter status_page');
$router->add('inverter/status.ajax', 'Inverter status_ajax');

// misc
$router->add('/',        'Misc main');
$router->add('sensors/', 'Misc sensors_page');
$router->add('pump/',    'Misc pump_page');
$router->add('phpinfo/', 'Misc phpinfo');


$route = routerFind($router);
if ($route === false)
    (new FakeRequestHandler)->dispatch('404');

list($handler, $act, $RouterInput) = $route;

$handler_class = $handler.'Handler';
if (!class_exists($handler_class)) {
    debugError('index.php: class '.$handler_class.' not found');
    (new FakeRequestHandler)->dispatch('404');
}

(new $handler_class)->dispatch($act);
