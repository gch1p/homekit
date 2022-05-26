<?php

class database {

    const SCHEMA_VERSION = 2;

    protected SQLite3 $link;

    public function __construct(string $db_path) {
        $this->link = new SQLite3($db_path);
        $this->link->enableExceptions(true);
        $this->upgradeSchema();
    }

    protected function upgradeSchema() {
        $cur = $this->getSchemaVersion();
        if ($cur < 1) {
            $this->link->exec("CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                password TEXT
            )");
        }
        if ($cur < 2) {
            $this->link->exec("CREATE TABLE vk_processed (
                last_message_time INTEGER
            )");
            $this->link->exec("INSERT INTO vk_processed (last_message_time) VALUES (0)");
        }
        $this->syncSchemaVersion();
    }

    protected function getSchemaVersion() {
        return $this->link->query("PRAGMA user_version")->fetchArray()[0];
    }

    protected function syncSchemaVersion() {
        $this->link->exec("PRAGMA user_version=".self::SCHEMA_VERSION);
    }

    protected function prepareQuery(string $sql): string {
        if (func_num_args() > 1) {
            $mark_count = substr_count($sql, '?');
            $positions = array();
            $last_pos = -1;
            for ($i = 0; $i < $mark_count; $i++) {
                $last_pos = strpos($sql, '?', $last_pos + 1);
                $positions[] = $last_pos;
            }
            for ($i = $mark_count - 1; $i >= 0; $i--) {
                $arg_val = func_get_arg($i + 1);
                if (is_null($arg_val)) {
                    $v = 'NULL';
                } else {
                    $v = '\''.$this->link->escapeString($arg_val) . '\'';
                }
                $sql = substr_replace($sql, $v, $positions[$i], 1);
            }
        }

        return $sql;
    }

    public function query(string $sql, ...$params): SQLite3Result {
        return $this->link->query($this->prepareQuery($sql, ...$params));
    }

    public function exec(string $sql, ...$params) {
        return $this->link->exec($this->prepareQuery($sql, ...$params));
    }

    public function querySingle(string $sql, ...$params) {
        return $this->link->querySingle($this->prepareQuery($sql, ...$params));
    }

    public function querySingleRow(string $sql, ...$params) {
        return $this->link->querySingle($this->prepareQuery($sql, ...$params), true);
    }

}