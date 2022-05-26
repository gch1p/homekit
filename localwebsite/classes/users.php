<?php

class users {

    public static function add(string $username, string $password): int {
        $db = getDB();
        $db->insert('users', [
            'username' => $username,
            'password' => pwhash($password)
        ]);
        return $db->insertId();
    }

    public static function exists(string $username): bool {
        $db = getDB();
        $count = (int)$db->querySingle("SELECT COUNT(*) FROM users WHERE username=?", $username);
        return $count > 0;
    }

    public static function validatePassword(string $username, string $password): bool {
        $db = getDB();
        $row = $db->querySingleRow("SELECT * FROM users WHERE username=?", $username);
        if (!$row)
            return false;

        return $row['password'] == pwhash($password);
    }

    public static function getUserByPwhash(string $pwhash): ?User {
        $db = getDB();
        $data = $db->querySingleRow("SELECT * FROM users WHERE password=?", $pwhash);
        return $data ? new User($data) : null;
    }

    public static function setPassword(int $id, string $new_password) {
        getDB()->exec("UPDATE users SET password=? WHERE id=?", pwhash($new_password), $id);
    }

}