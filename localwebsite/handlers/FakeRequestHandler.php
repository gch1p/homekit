<?php

class FakeRequestHandler extends RequestHandler {

    public function apacheNotFound() {
        http_response_code(404);
        $uri = htmlspecialchars($_SERVER['REQUEST_URI']);
        echo <<<EOF
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>404 Not Found</title>
</head><body>
<h1>Not Found</h1>
<p>The requested URL {$uri} was not found on this server.</p>
</body></html>
EOF;
        exit;
    }

}