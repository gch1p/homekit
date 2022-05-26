<?php

class User extends model {

    const DB_TABLE = 'users';

    public int $id;
    public string $username;
    public string $password;

}
