<?php

class AuthHandler extends RequestHandler {

    protected function before_dispatch(string $method, string $act) {
        return null;
    }

    public function GET_auth() {
        list($error) = $this->input('error');
        $this->tpl->set(['error' => $error]);
        $this->tpl->set_title('Авторизация');
        $this->tpl->render_page('auth.twig');
    }

    public function POST_auth() {
        list($username, $password) = $this->input('username, password');

        $result = users::validatePassword($username, $password);
        if (!$result) {
            debugError('invalid login attempt: '.$_SERVER['REMOTE_ADDR'].', '.$_SERVER['HTTP_USER_AGENT'].", username=$username, password=$password");
            redirect('/auth/?error='.urlencode('неверный логин или пароль'));
        }

        auth::setToken(pwhash($password));
        redirect('/');
    }

    public function GET_deauth() {
        if (auth::id())
            auth::logout();

        redirect('/');
    }

}
