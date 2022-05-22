<?php

abstract class base_tpl {

    public $twig;
    protected $vars = [];
    protected $global_vars = [];
    protected $title = '';
    protected $title_modifiers = [];
    protected $keywords = '';
    protected $description = '';
    protected $js = [];
    protected $lang_keys = [];
    protected $static = [];
    protected $external_static = [];
    protected $head = [];
    protected $globals_applied = false;
    protected $static_time;

    public function __construct($templates_dir, $cache_dir) {
        global $config;

        // $cl = get_called_class();

        $this->twig = self::twig_instance($templates_dir, $cache_dir, $config['is_dev']);
        $this->static_time = time();
    }

    public static function twig_instance($templates_dir, $cache_dir, $auto_reload) {
        // must specify a second argument ($rootPath) here
        // otherwise it will be getcwd() and it's www-prod/htdocs/ for apache and www-prod/ for cli code
        // this is bad for templates rebuilding
        $twig_loader = new \Twig\Loader\FilesystemLoader($templates_dir, ROOT);

        $env_options = [];
        if (!is_null($cache_dir)) {
            $env_options += [
                'cache' => $cache_dir,
                'auto_reload' => $auto_reload
            ];
        }

        $twig = new \Twig\Environment($twig_loader, $env_options);
        $twig->addExtension(new Twig_MyExtension);

        return $twig;
    }

    public function render($template, array $vars = []) {
        $this->apply_globals();
        return $this->do_render($template, array_merge($this->vars, $vars));
    }

    protected function do_render($template, $vars) {
        global $config;
        $s = '';
        try {
            $s = $this->twig->render($template, $vars);
        } catch (\Twig\Error\Error $e) {
            $error = get_class($e).": failed to render";
            $source_ctx = $e->getSourceContext();
            if ($source_ctx) {
                $path = $source_ctx->getPath();
                if (startsWith($path, ROOT))
                    $path = substr($path, strlen(ROOT)+1);
                $error .= " ".$source_ctx->getName()." (".$path.") at line ".$e->getTemplateLine();
            }
            $error .= ": ";
            $error .= $e->getMessage();
            debugError($error);
            if ($config['is_dev'])
                $s = $error."\n";
        }
        return $s;
    }

    public function set($arg1, $arg2 = null) {
        if (is_array($arg1)) {
            foreach ($arg1 as $key => $value) {
                $this->vars[$key] = $value;
            }
        } elseif ($arg2 !== null) {
            $this->vars[$arg1] = $arg2;
        }
    }

    public function is_set($key): bool {
        return isset($this->vars[$key]);
    }

    public function set_global($arg1, $arg2 = null) {
        if (is_array($arg1)) {
            foreach ($arg1 as $key => $value) {
                $this->global_vars[$key] = $value;
            }
        } elseif ($arg2 !== null) {
            $this->global_vars[$arg1] = $arg2;
        }
    }

    public function is_global_set($key): bool {
        return isset($this->global_vars[$key]);
    }

    public function get_global($key) {
        return $this->is_global_set($key) ? $this->global_vars[$key] : null;
    }

    public function apply_globals() {
        if (!empty($this->global_vars) && !$this->globals_applied) {
            foreach ($this->global_vars as $key => $value)
                $this->twig->addGlobal($key, $value);
            $this->globals_applied = true;
        }
    }

    /**
     * @param string $title
     */
    public function set_title($title) {
        $this->title = $title;
    }

    /**
     * @return string
     */
    public function get_title() {
        $title = $this->title != '' ? $this->title : 'Домашний сайт';
        if (!empty($this->title_modifiers)) {
            foreach ($this->title_modifiers as $modifier) {
                $title = $modifier($title);
            }
        }
        return $title;
    }

    /**
     * @param callable $callable
     */
    public function add_page_title_modifier(callable $callable) {
        if (!is_callable($callable)) {
            trigger_error(__METHOD__.': argument is not callable');
        } else {
            $this->title_modifiers[] = $callable;
        }
    }

    /**
     * @param string $css_name
     * @param null $extra
     */
    public function add_static(string $name, $extra = null) {
        global $config;
        // $is_css = endsWith($name, '.css');
        $this->static[] = [$name, $extra];
    }

    public function add_external_static($type, $url) {
        $this->external_static[] = ['type' => $type, 'url' => $url];
    }

    public function add_js($js) {
        $this->js[] = $js;
    }

    public function add_lang_keys(array $keys) {
        $this->lang_keys = array_merge($this->lang_keys, $keys);
    }

    public function add_head($html) {
        $this->head[] = $html;
    }

    public function get_head_html() {
        global $config;
        $lines = [];
        $public_path = $config['static_public_path'];
        foreach ($this->static as $val) {
            list($name, $extra) = $val;
            if (endsWith($name, '.js'))
                $lines[] = self::js_link($public_path.'/'.$name, $config['static'][$name] ?? 1);
            else
                $lines[] = self::css_link($public_path.'/'.$name, $config['static'][$name] ?? 1, $extra);
        }
        if (!empty($this->external_static)) {
            foreach ($this->external_static as $ext) {
                if ($ext['type'] == 'js')
                    $lines[] = self::js_link($ext['url']);
                else if ($ext['type'] == 'css')
                    $lines[] = self::css_link($ext['url']);
            }
        }
        if (!empty($this->head)) {
            $lines = array_merge($lines, $this->head);
        }
        return implode("\n", $lines);
    }

    public static function js_link($name, $version = null): string {
        if ($version !== null)
            $name .= '?'.$version;
        return '<script src="'.$name.'" type="text/javascript"></script>';
    }

    public static function css_link($name, $version = null, $extra = null) {
        if ($version !== null)
            $name .= '?'.$version;
        $s = '<link';
        if (is_array($extra)) {
            if (!empty($extra['id']))
                $s .= ' id="'.$extra['id'].'"';
        }
        $s .= ' rel="stylesheet" type="text/css"';
        if (is_array($extra) && !empty($extra['media']))
            $s .= ' media="'.$extra['media'].'"';
        $s .= ' href="'.$name.'"';
        $s .= '>';
        return $s;
    }

    public function get_lang_keys() {
        global $lang;
        $keys = [];
        if (!empty($this->lang_keys)) {
            foreach ($this->lang_keys as $key)
                $keys[$key] = $lang[$key];
        }
        return $keys;
    }

    public function render_not_found() {
        http_response_code(404);
        if (!is_xhr_request()) {
            $this->render_page('404.twig');
        } else {
            ajax_error(['code' => 404]);
        }
    }

    /**
     * @param null|string $reason
     */
    public function render_forbidden($reason = null) {
        http_response_code(403);
        if (!is_xhr_request()) {
            $this->set(['reason' => $reason]);
            $this->render_page('403.twig');
        } else {
            $data = ['code' => 403];
            if (!is_null($reason))
                $data['reason'] = $reason;
            ajax_error($data);
        }
    }

    public function must_revalidate() {
        header('Cache-Control: no-store, no-cache, must-revalidate');
    }

    abstract public function render_page($template);

}

class web_tpl extends base_tpl {

    protected $alternate = false;

    public function __construct() {
        global $config;
        $templates = $config['templates']['web'];
        parent::__construct(
            ROOT.'/'. $templates['root'],
            $config['twig_cache']
                ? ROOT.'/'.$templates['cache']
                : null
        );
    }

    public function set_alternate($alt) {
        $this->alternate = $alt;
    }

    public function render_page($template) {
        echo $this->_render_header();
        echo $this->_render_body($template);
        echo $this->_render_footer();
        exit;
    }

    public function _render_header() {
        global $config;
        $this->apply_globals();

        $vars = [
            'title' => $this->get_title(),
            'keywords' => $this->keywords,
            'description' => $this->description,
            'alternate' => $this->alternate,
            'static' => $this->get_head_html(),
        ];
        return $this->do_render('header.twig', $vars);
    }

    public function _render_body($template) {
        return $this->do_render($template, $this->vars);
    }

    public function _render_footer() {
        $exec_time = microtime(true) - START_TIME;
        $exec_time = round($exec_time, 4);

        $footer_vars = [
            'exec_time' => $exec_time,
            'js' => !empty($this->js) ? implode("\n", $this->js) : '',
        ];
        return $this->do_render('footer.twig', $footer_vars);
    }

}

class Twig_MyExtension extends \Twig\Extension\AbstractExtension {

    public function getFilters() {
        global $lang;

        return array(
            new \Twig\TwigFilter('lang', 'lang'),

            new \Twig\TwigFilter('lang', function($key, array $args = []) use (&$lang) {
                array_walk($args, function(&$item, $key) {
                    $item = htmlescape($item);
                });
                array_unshift($args, $key);
                return call_user_func_array([$lang, 'get'], $args);
            }, ['is_variadic' => true]),

            new \Twig\TwigFilter('plural', function($text, array $args = []) use (&$lang) {
                array_unshift($args, $text);
                return call_user_func_array([$lang, 'num'], $args);
            }, ['is_variadic' => true]),

            new \Twig\TwigFilter('format_number', function($number, array $args = []) {
                array_unshift($args, $number);
                return call_user_func_array('formatNumber', $args);
            }, ['is_variadic' => true]),

            new \Twig\TwigFilter('short_number', function($number, array $args = []) {
                array_unshift($args, $number);
                return call_user_func_array('shortNumber', $args);
            }, ['is_variadic']),

            new \Twig\TwigFilter('format_time', function($ts, array $args = []) {
                array_unshift($args, $ts);
                return call_user_func_array('formatTime', $args);
            }, ['is_variadic' => true]),

            new \Twig\TwigFilter('format_duration', function($seconds, array $args = []) {
                array_unshift($args, $seconds);
                return call_user_func_array('formatDuration', $args);
            }, ['is_variadic' => true]),
        );
    }

    public function getTokenParsers() {
        return [new JsTagTokenParser()];
    }

    public function getName() {
        return 'lang';
    }

}

// Based on https://stackoverflow.com/questions/26170727/how-to-create-a-twig-custom-tag-that-executes-a-callback
class JsTagTokenParser extends \Twig\TokenParser\AbstractTokenParser {

    public function parse(\Twig\Token $token) {
        $lineno = $token->getLine();
        $stream = $this->parser->getStream();

        // recovers all inline parameters close to your tag name
        $params = array_merge([], $this->getInlineParams($token));

        $continue = true;
        while ($continue) {
            // create subtree until the decideJsTagFork() callback returns true
            $body = $this->parser->subparse(array ($this, 'decideJsTagFork'));

            // I like to put a switch here, in case you need to add middle tags, such
            // as: {% js %}, {% nextjs %}, {% endjs %}.
            $tag = $stream->next()->getValue();
            switch ($tag) {
                case 'endjs':
                    $continue = false;
                    break;
                default:
                    throw new \Twig\Error\SyntaxError(sprintf('Unexpected end of template. Twig was looking for the following tags "endjs" to close the "mytag" block started at line %d)', $lineno), -1);
            }

            // you want $body at the beginning of your arguments
            array_unshift($params, $body);

            // if your endjs can also contains params, you can uncomment this line:
            // $params = array_merge($params, $this->getInlineParams($token));
            // and comment this one:
            $stream->expect(\Twig\Token::BLOCK_END_TYPE);
        }

        return new JsTagNode(new \Twig\Node\Node($params), $lineno, $this->getTag());
    }

    /**
     * Recovers all tag parameters until we find a BLOCK_END_TYPE ( %} )
     *
     * @param \Twig\Token $token
     * @return array
     */
    protected function getInlineParams(\Twig\Token $token) {
        $stream = $this->parser->getStream();
        $params = array ();
        while (!$stream->test(\Twig\Token::BLOCK_END_TYPE)) {
            $params[] = $this->parser->getExpressionParser()->parseExpression();
        }
        $stream->expect(\Twig\Token::BLOCK_END_TYPE);
        return $params;
    }

    /**
     * Callback called at each tag name when subparsing, must return
     * true when the expected end tag is reached.
     *
     * @param \Twig\Token $token
     * @return bool
     */
    public function decideJsTagFork(\Twig\Token $token) {
        return $token->test(['endjs']);
    }

    /**
     * Your tag name: if the parsed tag match the one you put here, your parse()
     * method will be called.
     *
     * @return string
     */
    public function getTag() {
        return 'js';
    }

}

class JsTagNode extends \Twig\Node\Node {

    public function __construct($params, $lineno = 0, $tag = null) {
        parent::__construct(['params' => $params], [], $lineno, $tag);
    }

    public function compile(\Twig\Compiler $compiler) {
        $count = count($this->getNode('params'));

        $compiler->addDebugInfo($this);
        $compiler
            ->write('global $__tpl;')
            ->raw(PHP_EOL);

        for ($i = 0; ($i < $count); $i++) {
            // argument is not an expression (such as, a \Twig\Node\Textbody)
            // we should trick with output buffering to get a valid argument to pass
            // to the functionToCall() function.
            if (!($this->getNode('params')->getNode($i) instanceof \Twig\Node\Expression\AbstractExpression)) {
                $compiler
                    ->write('ob_start();')
                    ->raw(PHP_EOL);

                $compiler
                    ->subcompile($this->getNode('params')->getNode($i));

                $compiler
                    ->write('$js = ob_get_clean();')
                    ->raw(PHP_EOL);
            }
        }

        $compiler
            ->write('$__tpl->add_js($js);')
            ->raw(PHP_EOL)
            ->write('unset($js);')
            ->raw(PHP_EOL);
    }

}



/**
 * @param $data
 */
function ajax_ok($data) {
    ajax_response(['response' => $data]);
}

/**
 * @param $error
 * @param int $code
 */
function ajax_error($error, $code = 200) {
    ajax_response(['error' => $error], $code);
}

/**
 * @param $data
 * @param int $code
 */
function ajax_response($data, $code = 200) {
    header('Cache-Control: no-cache, must-revalidate');
    header('Pragma: no-cache');
    header('Content-Type: application/json; charset=utf-8');
    http_response_code($code);
    echo jsonEncode($data);
    exit;
}