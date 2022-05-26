<?php

class auth {

    public static ?User $authorizedUser = null;

    const COOKIE_NAME = 'lws-auth';

    public static function getToken(): ?string {
        return $_COOKIE[self::COOKIE_NAME] ?? null;
    }

    public static function setToken(string $token) {
        setcookie_safe(self::COOKIE_NAME, $token);
    }

    public static function resetToken() {
        if (!headers_sent())
            unsetcookie(self::COOKIE_NAME);
    }

    public static function id(bool $do_check = true): int {
        if ($do_check)
            self::check();

        if (!self::$authorizedUser)
            return 0;

        return self::$authorizedUser->id;
    }

    public static function check(?string $pwhash = null): bool {
        if (self::$authorizedUser !== null)
            return true;

        // get auth token
        if (!$pwhash)
            $pwhash = self::getToken();

        if (!is_string($pwhash))
            return false;

        // find session by given token
        $user = users::getUserByPwhash($pwhash);
        if (is_null($user)) {
            self::resetToken();
            return false;
        }

        self::$authorizedUser = $user;

        return true;
    }

    public static function logout() {
        self::resetToken();
        self::$authorizedUser = null;
    }

}