import logging
import traceback

from html import escape
from telegram import (
    Update,
    ParseMode,
    ReplyKeyboardMarkup,
    CallbackQuery,
    User,
)
from telegram.ext import (
    Updater,
    Filters,
    BaseFilter,
    Handler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler
)
from telegram.error import TimedOut
from ..config import config
from typing import Optional, Union
from .store import Store
from .lang import LangPack
from ..api.types import BotType
from ..api import WebAPIClient
from .reporting import ReportingHelper

logger = logging.getLogger(__name__)
languages = {
    'en': 'English',
    'ru': 'Русский'
}
LANG_STARTED = range(1)
user_filter: Optional[BaseFilter] = None


def default_langpack() -> LangPack:
    lang = LangPack()
    lang.en(
        start_message="Select command on the keyboard.",
        unknown_message="Unknown message",
        cancel="Cancel",
        select_language="Select language on the keyboard.",
        invalid_language="Invalid language. Please try again.",
        language_saved='Saved.',
    )
    lang.ru(
        start_message="Выберите команду на клавиатуре.",
        unknown_message="Неизвестная команда",
        cancel="Отмена",
        select_language="Выберите язык на клавиатуре.",
        invalid_language="Неверный язык. Пожалуйста, попробуйте снова",
        language_saved="Настройки сохранены."
    )
    return lang


def init_user_filter():
    global user_filter
    if user_filter is None:
        if 'users' in config['bot']:
            logger.info('allowed users: ' + str(config['bot']['users']))
            user_filter = Filters.user(config['bot']['users'])
        else:
            user_filter = Filters.all  # not sure if this is correct


def text_filter(*args):
    init_user_filter()
    return Filters.text(args[0] if isinstance(args[0], list) else [*args]) & user_filter


def exc2text(e: Exception) -> str:
    tb = ''.join(traceback.format_tb(e.__traceback__))
    return f'{e.__class__.__name__}: ' + escape(str(e)) + "\n\n" + escape(tb)


class IgnoreMarkup:
    pass


class Context:
    _update: Optional[Update]
    _callback_context: Optional[CallbackContext]
    _markup_getter: callable
    _lang: LangPack
    _store: Optional[Store]
    _user_lang: Optional[str]

    def __init__(self,
                 update: Optional[Update],
                 callback_context: Optional[CallbackContext],
                 markup_getter: callable,
                 lang: LangPack,
                 store: Optional[Store]):
        self._update = update
        self._callback_context = callback_context
        self._markup_getter = markup_getter
        self._lang = lang
        self._store = store
        self._user_lang = None

    def reply(self, text, markup=None):
        if markup is None:
            markup = self._markup_getter(self)
        kwargs = dict(parse_mode=ParseMode.HTML)
        if not isinstance(markup, IgnoreMarkup):
            kwargs['reply_markup'] = markup
        self._update.message.reply_text(text, **kwargs)

    def reply_exc(self, e: Exception) -> None:
        self.reply(exc2text(e))

    def answer(self, text: str = None):
        self.callback_query.answer(text)

    def edit(self, text, markup=None):
        kwargs = dict(parse_mode=ParseMode.HTML)
        if not isinstance(markup, IgnoreMarkup):
            kwargs['reply_markup'] = markup
        self.callback_query.edit_message_text(text, **kwargs)

    @property
    def text(self) -> str:
        return self._update.message.text

    @property
    def callback_query(self) -> CallbackQuery:
        return self._update.callback_query

    @property
    def args(self) -> Optional[list[str]]:
        return self._callback_context.args

    @property
    def user_id(self) -> int:
        return self.user.id

    @property
    def user(self) -> User:
        return self._update.effective_user

    @property
    def user_lang(self) -> str:
        if self._user_lang is None:
            self._user_lang = self._store.get_user_lang(self.user_id)
        return self._user_lang

    def lang(self, key: str, *args) -> str:
        return self._lang.get(key, self.user_lang, *args)

    def is_callback_context(self) -> bool:
        return self._update.callback_query and self._update.callback_query.data and self._update.callback_query.data != ''


class Wrapper:
    store: Optional[Store]
    updater: Updater
    lang: LangPack
    reporting: Optional[ReportingHelper]

    def __init__(self):
        self.updater = Updater(config['bot']['token'],
                               request_kwargs={'read_timeout': 6, 'connect_timeout': 7})
        self.lang = default_langpack()
        self.store = Store()
        self.reporting = None

        init_user_filter()

        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(CommandHandler('start', self.wrap(self.start), user_filter))

        # transparently log all messages
        self.add_handler(MessageHandler(Filters.all & user_filter, self.logging_message_handler), group=10)
        self.add_handler(CallbackQueryHandler(self.logging_callback_handler), group=10)

    def run(self):
        self._lang_setup()
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.all & user_filter, self.wrap(self.any))
        )

        # start the bot
        self.updater.start_polling()

        # run the bot until the user presses Ctrl-C or the process receives SIGINT, SIGTERM or SIGABRT
        self.updater.idle()

    def enable_logging(self, bot_type: BotType):
        api = WebAPIClient(timeout=3)
        api.enable_async()

        self.reporting = ReportingHelper(api, bot_type)

    def logging_message_handler(self, update: Update, context: CallbackContext):
        if self.reporting is None:
            return

        self.reporting.report(update.message)

    def logging_callback_handler(self, update: Update, context: CallbackContext):
        if self.reporting is None:
            return

        self.reporting.report(update.callback_query.message, text=update.callback_query.data)

    def wrap(self, f: callable):
        def handler(update: Update, context: CallbackContext):
            ctx = Context(update,
                          callback_context=context,
                          markup_getter=self.markup,
                          lang=self.lang,
                          store=self.store)

            try:
                return f(ctx)
            except Exception as e:
                if not self.exception_handler(e, ctx) and not isinstance(e, TimedOut):
                    logger.exception(e)
                    if not ctx.is_callback_context():
                        ctx.reply_exc(e)
                    else:
                        self.notify_user(ctx.user_id, exc2text(e))

        return handler

    def add_handler(self, handler: Handler, group=0):
        self.updater.dispatcher.add_handler(handler, group=group)

    def start(self, ctx: Context):
        if 'start_message' not in self.lang:
            ctx.reply('Please define start_message or override start()')
            return

        ctx.reply(ctx.lang('start_message'))

    def any(self, ctx: Context):
        if 'invalid_command' not in self.lang:
            ctx.reply('Please define invalid_command or override any()')
            return

        ctx.reply(ctx.lang('invalid_command'))

    def markup(self, ctx: Optional[Context]) -> Optional[ReplyKeyboardMarkup]:
        return None

    def exception_handler(self, e: Exception, ctx: Context) -> Optional[bool]:
        pass

    def notify_all(self, text_getter: callable, exclude: tuple[int] = ()) -> None:
        if 'notify_users' not in config['bot']:
            logger.error('notify_all() called but no notify_users directive found in the config')
            return

        for user_id in config['bot']['notify_users']:
            if user_id in exclude:
                continue

            text = text_getter(self.store.get_user_lang(user_id))
            self.updater.bot.send_message(chat_id=user_id,
                                          text=text,
                                          parse_mode='HTML')

    def notify_user(self, user_id: int, text: Union[str, Exception]) -> None:
        if isinstance(text, Exception):
            text = exc2text(text)
        self.updater.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')

    def send_photo(self, user_id, **kwargs):
        self.updater.bot.send_photo(chat_id=user_id, **kwargs)

    def send_audio(self, user_id, **kwargs):
        self.updater.bot.send_audio(chat_id=user_id, **kwargs)

    def send_file(self, user_id, **kwargs):
        self.updater.bot.send_document(chat_id=user_id, **kwargs)

    #
    # Language Selection
    #

    def _lang_setup(self):
        supported = self.lang.languages
        if len(supported) > 1:
            cancel_filter = Filters.text(self.lang.all('cancel'))

            self.add_handler(ConversationHandler(
                entry_points=[CommandHandler('lang', self.wrap(self._lang_command), user_filter)],
                states={
                    LANG_STARTED: [
                        *list(map(lambda key: MessageHandler(text_filter(languages[key]),
                                                             self.wrap(self._lang_input)), supported)),
                        MessageHandler(user_filter & ~cancel_filter, self.wrap(self._lang_invalid_input))
                    ]
                },
                fallbacks=[MessageHandler(user_filter & cancel_filter, self.wrap(self._lang_cancel_input))]
            ))

    def _lang_command(self, ctx: Context):
        logger.debug(f'current language: {ctx.user_lang}')

        buttons = []
        for name in languages.values():
            buttons.append(name)
        markup = ReplyKeyboardMarkup([buttons, [ctx.lang('cancel')]], one_time_keyboard=False)

        ctx.reply(ctx.lang('select_language'), markup=markup)
        return LANG_STARTED

    def _lang_input(self, ctx: Context):
        lang = None
        for key, value in languages.items():
            if value == ctx.text:
                lang = key
                break

        if lang is None:
            ValueError('could not find the language')

        self.store.set_user_lang(ctx.user_id, lang)

        ctx.reply(ctx.lang('language_saved'), markup=IgnoreMarkup())

        self.start(ctx)
        return ConversationHandler.END

    def _lang_invalid_input(self, ctx: Context):
        ctx.reply(self.lang('invalid_language'), markup=IgnoreMarkup())
        return LANG_STARTED

    def _lang_cancel_input(self, ctx: Context):
        self.start(ctx)
        return ConversationHandler.END

    @property
    def user_filter(self):
        return user_filter
