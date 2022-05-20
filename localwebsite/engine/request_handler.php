<?php

abstract class request_handler {

    const GET = 'GET';
    const POST = 'POST';

    private static array $AllowedInputTypes = ['i', 'f', 'b', 'e' /* enum */];

    public function dispatch(string $act) {
        $method = $_SERVER['REQUEST_METHOD'] == 'POST' ? 'POST' : 'GET';
        return $this->call_act($method, $act);
    }

    protected function before_dispatch(string $method, string $act)/*: ?array*/ {
        return null;
    }

    protected function call_act(string $method, string $act, array $input = []) {
        global $RouterInput;

        $notfound = !method_exists($this, $method.'_'.$act) || !((new ReflectionMethod($this, $method.'_'.$act))->isPublic());
        if ($notfound)
            $this->method_not_found($method, $act);

        if (!empty($input)) {
            foreach ($input as $k => $v)
                $RouterInput[$k] = $v;
        }

        $args = $this->before_dispatch($method, $act);
        return call_user_func_array([$this, $method.'_'.$act], is_array($args) ? [$args] : []);
    }

    abstract protected function method_not_found(string $method, string $act);

    protected function input(string $input, bool $as_assoc = false): array {
        $input = preg_split('/,\s+?/', $input, null, PREG_SPLIT_NO_EMPTY);

        $ret = [];
        foreach ($input as $var) {
            list($type, $name, $enum_values, $enum_default) = self::parse_input_var($var);

            $value = param($name);

            switch ($type) {
                case 'i':
                    if (is_null($value) && !is_null($enum_default)) {
                        $value = (int)$enum_default;
                    } else {
                        $value = (int)$value;
                    }
                    break;

                case 'f':
                    if (is_null($value) && !is_null($enum_default)) {
                        $value = (float)$enum_default;
                    } else {
                        $value = (float)$value;
                    }
                    break;

                case 'b':
                    if (is_null($value) && !is_null($enum_default)) {
                        $value = (bool)$enum_default;
                    } else {
                        $value = (bool)$value;
                    }
                    break;

                case 'e':
                    if (!in_array($value, $enum_values)) {
                        $value = !is_null($enum_default) ? $enum_default : '';
                    }
                    break;
            }

            if (!$as_assoc) {
                $ret[] = $value;
            } else {
                $ret[$name] = $value;
            }
        }

        return $ret;
    }
    protected static function parse_input_var(string $var): array {
        $type = null;
        $name = null;
        $enum_values = null;
        $enum_default = null;

        $pos = strpos($var, ':');
        if ($pos !== false) {
            $type = substr($var, 0, $pos);
            $rest = substr($var, $pos+1);

            if (!in_array($type, self::$AllowedInputTypes)) {
                trigger_error('request_handler::parse_input_var('.$var.'): unknown type '.$type);
                $type = null;
            }

            switch ($type) {
                case 'e':
                    $br_from = strpos($rest, '(');
                    $br_to = strpos($rest, ')');

                    if ($br_from === false || $br_to === false) {
                        trigger_error('request_handler::parse_input_var('.$var.'): failed to parse enum values');
                        $type = null;
                        $name = $rest;
                        break;
                    }

                    $enum_values = array_map('trim', explode('|', trim(substr($rest, $br_from+1, $br_to-$br_from-1))));
                    $name = trim(substr($rest, 0, $br_from));

                    if (!empty($enum_values)) foreach ($enum_values as $key => $val) {
                        if (substr($val, 0, 1) == '=') {
                            $enum_values[$key] = substr($val, 1);
                            $enum_default = $enum_values[$key];
                        }
                    }
                    break;

                default:
                    if (($eq_pos = strpos($rest, '=')) !== false) {
                        $enum_default = substr($rest, $eq_pos+1);
                        $rest = substr($rest, 0, $eq_pos);
                    }
                    $name = trim($rest);
                    break;
            }
        } else {
            $type = 's';
            $name = $var;
        }

        return [$type, $name, $enum_values, $enum_default];
    }

}
