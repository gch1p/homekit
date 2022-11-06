from typing import Optional, List

from telegram import Update, ParseMode, User, CallbackQuery
from telegram.ext import CallbackContext

from ._botdb import BotDatabase
from ._botlang import lang
from ._botutil import IgnoreMarkup, exc2text


class Context:
    _update: Optional[Update]
    _callback_context: Optional[CallbackContext]
    _markup_getter: callable
    db: Optional[BotDatabase]
    _user_lang: Optional[str]

    def __init__(self,
                 update: Optional[Update],
                 callback_context: Optional[CallbackContext],
                 markup_getter: callable,
                 store: Optional[BotDatabase]):
        self._update = update
        self._callback_context = callback_context
        self._markup_getter = markup_getter
        self._store = store
        self._user_lang = None

    def reply(self, text, markup=None):
        if markup is None:
            markup = self._markup_getter(self)
        kwargs = dict(parse_mode=ParseMode.HTML)
        if not isinstance(markup, IgnoreMarkup):
            kwargs['reply_markup'] = markup
        return self._update.message.reply_text(text, **kwargs)

    def reply_exc(self, e: Exception) -> None:
        self.reply(exc2text(e), markup=IgnoreMarkup())

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
    def args(self) -> Optional[List[str]]:
        return self._callback_context.args

    @property
    def user_id(self) -> int:
        return self.user.id

    @property
    def user_data(self):
        return self._callback_context.user_data

    @property
    def user(self) -> User:
        return self._update.effective_user

    @property
    def user_lang(self) -> str:
        if self._user_lang is None:
            self._user_lang = self._store.get_user_lang(self.user_id)
        return self._user_lang

    def lang(self, key: str, *args) -> str:
        return lang.get(key, self.user_lang, *args)

    def is_callback_context(self) -> bool:
        return self._update.callback_query \
               and self._update.callback_query.data \
               and self._update.callback_query.data != ''
