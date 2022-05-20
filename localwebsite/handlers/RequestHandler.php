<?php

class RequestHandler extends request_handler {

    /** @var web_tpl*/
    protected $tpl;

    public function __construct() {
        global $__tpl;
        $__tpl = new web_tpl();
        $this->tpl = $__tpl;

        $this->tpl->add_static('bootstrap.min.css');
        $this->tpl->add_static('bootstrap.min.js');
        $this->tpl->add_static('polyfills.js');
        $this->tpl->add_static('app.js');
        $this->tpl->add_static('app.css');
    }

    public function dispatch(string $act) {
        global $config;
        $this->tpl->set_global([
            '__dev' => $config['is_dev'],
        ]);
        return parent::dispatch($act);
    }

    protected function method_not_found(string $method, string $act)
    {
        global $config;

        if ($act != '404' && $config['is_dev'])
            debugError(get_called_class() . ": act {$method}_{$act} not found.");

        if (!is_xhr_request())
            $this->tpl->render_not_found();
        else
            ajax_error('unknown act "'.$act.'"', 404);

    }
}