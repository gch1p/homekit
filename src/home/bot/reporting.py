import logging

from telegram import Message
from ..api import WebAPIClient as APIClient
from ..api.errors import ApiResponseError
from ..api.types import BotType

logger = logging.getLogger(__name__)


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
            logger.exception(error)
