import logging
import traceback

from html import escape
from telegram import User
from home.api import WebAPIClient as APIClient
from home.api.types import BotType
from home.api.errors import ApiResponseError

_logger = logging.getLogger(__name__)


def user_any_name(user: User) -> str:
    name = [user.first_name, user.last_name]
    name = list(filter(lambda s: s is not None, name))
    name = ' '.join(name).strip()

    if not name:
        name = user.username

    if not name:
        name = str(user.id)

    return name


class ReportingHelper:
    def __init__(self, client: APIClient, bot_type: BotType):
        self.client = client
        self.bot_type = bot_type

    def report(self, message, text: str = None) -> None:
        if text is None:
            text = message.text
        try:
            self.client.log_bot_request(self.bot_type, message.chat_id, text)
        except ApiResponseError as error:
            _logger.exception(error)


def exc2text(e: Exception) -> str:
    tb = ''.join(traceback.format_tb(e.__traceback__))
    return f'{e.__class__.__name__}: ' + escape(str(e)) + "\n\n" + escape(tb)


class IgnoreMarkup:
    pass
