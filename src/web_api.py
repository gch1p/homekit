#!/usr/bin/env python3
from home.web_api import get_app
from typing import Optional
from flask import Flask

app: Optional[Flask] = None


if __name__ in ('__main__', 'app'):
    app = get_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
