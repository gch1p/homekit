<?php

abstract class model {

    const DB_TABLE = null;
    const DB_KEY = 'id';

    const STRING     = 0;
    const INTEGER    = 1;
    const FLOAT      = 2;
    const ARRAY      = 3;
    const BOOLEAN    = 4;
    const JSON       = 5;
    const SERIALIZED = 6;

    protected static array $SpecCache = [];

    public static function create_instance(...$args) {
        $cl = get_called_class();
        return new $cl(...$args);
    }

    public function __construct(array $raw) {
        if (!isset(self::$SpecCache[static::class])) {
            list($fields, $model_name_map, $db_name_map) = static::get_spec();
            self::$SpecCache[static::class] = [
                'fields' => $fields,
                'model_name_map' => $model_name_map,
                'db_name_map' => $db_name_map
            ];
        }

        foreach (self::$SpecCache[static::class]['fields'] as $field)
            $this->{$field['model_name']} = self::cast_to_type($field['type'], $raw[$field['db_name']]);

        if (is_null(static::DB_TABLE))
            trigger_error('class '.get_class($this).' doesn\'t have DB_TABLE defined');
    }

    /**
     * @param $fields
     *
     * TODO: support adding or subtracting (SET value=value+1)
     */
    public function edit($fields) {
        $db = getDB();

        $model_upd = [];
        $db_upd = [];

        foreach ($fields as $name => $value) {
            $index = self::$SpecCache[static::class]['db_name_map'][$name] ?? null;
            if (is_null($index)) {
                debugError(__METHOD__.': field `'.$name.'` not found in '.static::class);
                continue;
            }

            $field = self::$SpecCache[static::class]['fields'][$index];
            switch ($field['type']) {
                case self::ARRAY:
                    if (is_array($value)) {
                        $db_upd[$name] = implode(',', $value);
                        $model_upd[$field['model_name']] = $value;
                    } else {
                        debugError(__METHOD__.': field `'.$name.'` is expected to be array. skipping.');
                    }
                    break;

                case self::INTEGER:
                    $value = (int)$value;
                    $db_upd[$name] = $value;
                    $model_upd[$field['model_name']] = $value;
                    break;

                case self::FLOAT:
                    $value = (float)$value;
                    $db_upd[$name] = $value;
                    $model_upd[$field['model_name']] = $value;
                    break;

                case self::BOOLEAN:
                    $db_upd[$name] = $value ? 1 : 0;
                    $model_upd[$field['model_name']] = $value;
                    break;

                case self::JSON:
                    $db_upd[$name] = jsonEncode($value);
                    $model_upd[$field['model_name']] = $value;
                    break;

                case self::SERIALIZED:
                    $db_upd[$name] = serialize($value);
                    $model_upd[$field['model_name']] = $value;
                    break;

                default:
                    $value = (string)$value;
                    $db_upd[$name] = $value;
                    $model_upd[$field['model_name']] = $value;
                    break;
            }
        }

        if (!empty($db_upd) && !$db->update(static::DB_TABLE, $db_upd, static::DB_KEY."=?", $this->get_id())) {
            debugError(__METHOD__.': failed to update database');
            return;
        }

        if (!empty($model_upd)) {
            foreach ($model_upd as $name => $value)
                $this->{$name} = $value;
        }
    }

    public function get_id() {
        return $this->{to_camel_case(static::DB_KEY)};
    }

    public function as_array(array $fields = [], array $custom_getters = []): array {
        if (empty($fields))
            $fields = array_keys(static::$SpecCache[static::class]['db_name_map']);

        $array = [];
        foreach ($fields as $field) {
            if (isset($custom_getters[$field]) && is_callable($custom_getters[$field])) {
                $array[$field] = $custom_getters[$field]();
            } else {
                $array[$field] = $this->{to_camel_case($field)};
            }
        }

        return $array;
    }

    protected static function cast_to_type(int $type, $value) {
        switch ($type) {
            case self::BOOLEAN:
                return (bool)$value;

            case self::INTEGER:
                return (int)$value;

            case self::FLOAT:
                return (float)$value;

            case self::ARRAY:
                return array_filter(explode(',', $value));

            case self::JSON:
                $val = jsonDecode($value);
                if (!$val)
                    $val = null;
                return $val;

            case self::SERIALIZED:
                $val = unserialize($value);
                if ($val === false)
                    $val = null;
                return $val;

            default:
                return (string)$value;
        }
    }

    protected static function get_spec(): array {
        $rc = new ReflectionClass(static::class);
        $props = $rc->getProperties(ReflectionProperty::IS_PUBLIC);

        $list = [];
        $index = 0;

        $model_name_map = [];
        $db_name_map = [];

        foreach ($props as $prop) {
            if ($prop->isStatic())
                continue;

            $name = $prop->getName();
            if (startsWith($name, '_'))
                continue;

            $type = $prop->getType();
            $phpdoc = $prop->getDocComment();

            $mytype = null;
            if (!$prop->hasType() && !$phpdoc)
                $mytype = self::STRING;
            else {
                $typename = $type->getName();
                switch ($typename) {
                    case 'string':
                        $mytype = self::STRING;
                        break;
                    case 'int':
                        $mytype = self::INTEGER;
                        break;
                    case 'float':
                        $mytype = self::FLOAT;
                        break;
                    case 'array':
                        $mytype = self::ARRAY;
                        break;
                    case 'bool':
                        $mytype = self::BOOLEAN;
                        break;
                }

                if ($phpdoc != '') {
                    $pos = strpos($phpdoc, '@');
                    if ($pos === false)
                        continue;

                    if (substr($phpdoc, $pos+1, 4) == 'json')
                        $mytype = self::JSON;
                    else if (substr($phpdoc, $pos+1, 5) == 'array')
                        $mytype = self::ARRAY;
                    else if (substr($phpdoc, $pos+1, 10) == 'serialized')
                        $mytype = self::SERIALIZED;
                }
            }

            if (is_null($mytype))
                debugError(__METHOD__.": ".$name." is still null in ".static::class);

            $dbname = from_camel_case($name);
            $list[] = [
                'type' => $mytype,
                'model_name' => $name,
                'db_name' => $dbname
            ];

            $model_name_map[$name] = $index;
            $db_name_map[$dbname] = $index;

            $index++;
        }

        return [$list, $model_name_map, $db_name_map];
    }

}
