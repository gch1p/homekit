import requests
import logging

from ..config import config


_logger = logging.getLogger(__name__)


def send_message(text: str,
                  parse_mode: str = None,
                  disable_web_page_preview: bool = False):
    data, token = _send_telegram_data(text, parse_mode, disable_web_page_preview)
    req = requests.post('https://api.telegram.org/bot%s/sendMessage' % token, data=data)
    return req.json()


def send_photo(filename: str):
    data = {
        'chat_id': config['telegram']['chat_id'],
    }
    token = config['telegram']['token']

    url = f'https://api.telegram.org/bot{token}/sendPhoto'
    with open(filename, "rb") as fd:
        req = requests.post(url, data=data, files={"photo": fd})
    return req.json()


def _send_telegram_data(text: str,
                        parse_mode: str = None,
                        disable_web_page_preview: bool = False) -> tuple[dict, str]:
    data = {
        'chat_id': config['telegram']['chat_id'],
        'text': text
    }

    if parse_mode is not None:
        data['parse_mode'] = parse_mode
    elif 'parse_mode' in config['telegram']:
        data['parse_mode'] = config['telegram']['parse_mode']

    if disable_web_page_preview or 'disable_web_page_preview' in config['telegram']:
        data['disable_web_page_preview'] = 1

    return data, config['telegram']['token']
