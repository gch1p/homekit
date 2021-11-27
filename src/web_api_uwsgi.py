#!/usr/bin/env python3
from home.web_api import get_app

app = get_app()


if __name__ == '__main__':
    app.run()
