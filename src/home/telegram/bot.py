from __future__ import annotations

import logging
import itertools

from enum import Enum, auto
from functools import wraps
from typing import Optional, Union, Tuple

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    Filters,
    BaseFilter,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler
)
from telegram.error import TimedOut

from home.config import config
from home.api import WebAPIClient
from home.api.types import BotType

from ._botlang import lang, languages
from ._botdb import BotDatabase
from ._botutil import ReportingHelper, exc2text, IgnoreMarkup, user_any_name
from ._botcontext import Context


db: Optional[BotDatabase] = None

_user_filter: Optional[BaseFilter] = None
_cancel_filter = Filters.text(lang.all('cancel'))
_back_filter = Filters.text(lang.all('back'))
_cancel_and_back_filter = Filters.text(lang.all('back') + lang.all('cancel'))

_logger = logging.getLogger(__name__)
_updater: Optional[Updater] = None
_reporting: Optional[ReportingHelper] = None
_exception_handler: Optional[callable] = None
_dispatcher = None
_markup_getter: Optional[callable] = None
_start_handler_ref: Optional[callable] = None


def text_filter(*args):
    if not _user_filter:
        raise RuntimeError('user_filter is not initialized')
    return Filters.text(args[0] if isinstance(args[0], list) else [*args]) & _user_filter


def _handler_of_handler(*args, **kwargs):
    self = None
    context = None
    update = None

    _args = list(args)
    while len(_args):
        v = _args[0]
        if isinstance(v, conversation):
            self = v
            _args.pop(0)
        elif isinstance(v, Update):
            update = v
            _args.pop(0)
        elif isinstance(v, CallbackContext):
            context = v
            _args.pop(0)
            break

    ctx = Context(update,
                  callback_context=context,
                  markup_getter=lambda _ctx: None if not _markup_getter else _markup_getter(_ctx),
                  store=db)
    try:
        _args.insert(0, ctx)

        f = kwargs['f']
        del kwargs['f']

        if 'return_with_context' in kwargs:
            return_with_context = True
            del kwargs['return_with_context']
        else:
            return_with_context = False

        if 'argument' in kwargs and kwargs['argument'] == 'message_key':
            del kwargs['argument']
            mkey = None
            for k, v in lang.get_langpack(ctx.user_lang).items():
                if ctx.text == v:
                    mkey = k
                    break
            _args.insert(0, mkey)

        if self:
            _args.insert(0, self)

        result = f(*_args, **kwargs)
        return result if not return_with_context else (result, ctx)

    except Exception as e:
        if _exception_handler:
            if not _exception_handler(e, ctx) and not isinstance(e, TimedOut):
                _logger.exception(e)
                if not ctx.is_callback_context():
                    ctx.reply_exc(e)
                else:
                    notify_user(ctx.user_id, exc2text(e))
        else:
            _logger.exception(e)


def handler(**kwargs):
    def inner(f):
        @wraps(f)
        def _handler(*args, **inner_kwargs):
            if 'argument' in kwargs and kwargs['argument'] == 'message_key':
                inner_kwargs['argument'] = 'message_key'
            return _handler_of_handler(f=f, *args, **inner_kwargs)

        messages = []
        texts = []

        if 'messages' in kwargs:
            messages += kwargs['messages']
        if 'message' in kwargs:
            messages.append(kwargs['message'])

        if 'text' in kwargs:
            texts.append(kwargs['text'])
        if 'texts' in kwargs:
            texts.append(kwargs['texts'])

        if messages:
            texts = list(itertools.chain.from_iterable([lang.all(m) for m in messages]))

        _updater.dispatcher.add_handler(
            MessageHandler(text_filter(*texts), _handler),
            group=0
        )

        if 'command' in kwargs:
            _updater.dispatcher.add_handler(CommandHandler(kwargs['command'], _handler), group=0)

        if 'callback' in kwargs:
            _updater.dispatcher.add_handler(CallbackQueryHandler(_handler, pattern=kwargs['callback']), group=0)

        return _handler

    return inner


def simplehandler(f: callable):
    @wraps(f)
    def _handler(*args, **kwargs):
        return _handler_of_handler(f=f, *args, **kwargs)
    return _handler


def callbackhandler(*args, **kwargs):
    def inner(f):
        @wraps(f)
        def _handler(*args, **kwargs):
            return _handler_of_handler(f=f, *args, **kwargs)
        pattern_kwargs = {}
        if kwargs['callback'] != '*':
            pattern_kwargs['pattern'] = kwargs['callback']
        _updater.dispatcher.add_handler(CallbackQueryHandler(_handler, **pattern_kwargs), group=0)
        return _handler
    return inner


def exceptionhandler(f: callable):
    global _exception_handler
    if _exception_handler:
        _logger.warning('exception handler already set, we will overwrite it')
    _exception_handler = f


def defaultreplymarkup(f: callable):
    global _markup_getter
    _markup_getter = f


def convinput(state, is_enter=False, **kwargs):
    def inner(f):
        f.__dict__['_conv_data'] = dict(
            orig_f=f,
            enter=is_enter,
            type=ConversationMethodType.ENTRY if is_enter and state == 0 else ConversationMethodType.STATE_HANDLER,
            state=state,
            **kwargs
        )

        @wraps(f)
        def _impl(*args, **kwargs):
            result, ctx = _handler_of_handler(f=f, *args, **kwargs, return_with_context=True)
            if result == conversation.END:
                start(ctx)
            return result

        return _impl

    return inner


def conventer(state, **kwargs):
    return convinput(state, is_enter=True, **kwargs)


class ConversationMethodType(Enum):
    ENTRY = auto()
    STATE_HANDLER = auto()


class conversation:
    END = ConversationHandler.END
    STATE_SEQS = []

    def __init__(self, enable_back=False):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._user_state_cache = {}
        self._back_enabled = enable_back

    def make_handlers(self, f: callable, **kwargs) -> list:
        messages = {}
        handlers = []

        if 'messages' in kwargs:
            if isinstance(kwargs['messages'], dict):
                messages = kwargs['messages']
            else:
                for m in kwargs['messages']:
                    messages[m] = None

        if 'message' in kwargs:
            if isinstance(kwargs['message'], str):
                messages[kwargs['message']] = None
            else:
                AttributeError('invalid message type: ' + type(kwargs['message']))

        if messages:
            for message, target_state in messages.items():
                if not target_state:
                    handlers.append(MessageHandler(text_filter(lang.all(message) if 'messages_lang_completed' not in kwargs else message), f))
                else:
                    handlers.append(MessageHandler(text_filter(lang.all(message) if 'messages_lang_completed' not in kwargs else message), self.make_invoker(target_state)))

        if 'regex' in kwargs:
            handlers.append(MessageHandler(Filters.regex(kwargs['regex']) & _user_filter, f))

        if 'command' in kwargs:
            handlers.append(CommandHandler(kwargs['command'], f, _user_filter))

        return handlers

    def make_invoker(self, state):
        def _invoke(update: Update, context: CallbackContext):
            ctx = Context(update,
                          callback_context=context,
                          markup_getter=lambda _ctx: None if not _markup_getter else _markup_getter(_ctx),
                          store=db)
            return self.invoke(state, ctx)
        return _invoke

    def invoke(self, state, ctx: Context):
        self._logger.debug(f'invoke, state={state}')
        for item in dir(self):
            f = getattr(self, item)
            if not callable(f) or item.startswith('_') or '_conv_data' not in f.__dict__:
                continue
            cd = f.__dict__['_conv_data']
            if cd['enter'] and cd['state'] == state:
                return cd['orig_f'](self, ctx)

        raise RuntimeError(f'invoke: failed to find method for state {state}')

    def get_handler(self) -> ConversationHandler:
        entry_points = []
        states = {}

        l_cancel_filter = _cancel_filter if not self._back_enabled else _cancel_and_back_filter

        for item in dir(self):
            f = getattr(self, item)
            if not callable(f) or item.startswith('_') or '_conv_data' not in f.__dict__:
                continue

            cd = f.__dict__['_conv_data']

            if cd['type'] == ConversationMethodType.ENTRY:
                entry_points = self.make_handlers(f, **cd)
            elif cd['type'] == ConversationMethodType.STATE_HANDLER:
                states[cd['state']] = self.make_handlers(f, **cd)
                states[cd['state']].append(
                    MessageHandler(_user_filter & ~l_cancel_filter, conversation.invalid)
                )

        fallbacks = [MessageHandler(_user_filter & _cancel_filter, self.cancel)]
        if self._back_enabled:
            fallbacks.append(MessageHandler(_user_filter & _back_filter, self.back))

        return ConversationHandler(
            entry_points=entry_points,
            states=states,
            fallbacks=fallbacks
        )

    def get_user_state(self, user_id: int) -> Optional[int]:
        if user_id not in self._user_state_cache:
            return None
        return self._user_state_cache[user_id]

    # TODO store in ctx.user_state
    def set_user_state(self, user_id: int, state: Union[int, None]):
        if not self._back_enabled:
            return
        if state is not None:
            self._user_state_cache[user_id] = state
        else:
            del self._user_state_cache[user_id]

    @staticmethod
    @simplehandler
    def invalid(ctx: Context):
        ctx.reply(ctx.lang('invalid_input'), markup=IgnoreMarkup())
        # return 0  # FIXME is this needed

    @simplehandler
    def cancel(self, ctx: Context):
        start(ctx)
        self.set_user_state(ctx.user_id, None)
        return conversation.END

    @simplehandler
    def back(self, ctx: Context):
        cur_state = self.get_user_state(ctx.user_id)
        if cur_state is None:
            start(ctx)
            self.set_user_state(ctx.user_id, None)
            return conversation.END

        new_state = None
        for seq in self.STATE_SEQS:
            if cur_state in seq:
                idx = seq.index(cur_state)
                if idx > 0:
                    return self.invoke(seq[idx-1], ctx)

        if new_state is None:
            raise RuntimeError('failed to determine state to go back to')

    @classmethod
    def add_cancel_button(cls, ctx: Context, buttons):
        buttons.append([ctx.lang('cancel')])

    @classmethod
    def add_back_button(cls, ctx: Context, buttons):
        # buttons.insert(0, [ctx.lang('back')])
        buttons.append([ctx.lang('back')])

    def reply(self,
              ctx: Context,
              state: Union[int, Enum],
              text: str,
              buttons: Optional[list],
              with_cancel=False,
              with_back=False,
              buttons_lang_completed=False):

        if buttons:
            new_buttons = []
            if not buttons_lang_completed:
                for item in buttons:
                    if isinstance(item, list):
                        item = map(lambda s: ctx.lang(s), item)
                        new_buttons.append(list(item))
                    elif isinstance(item, str):
                        new_buttons.append([ctx.lang(item)])
                    else:
                        raise ValueError('invalid type: ' + type(item))
            else:
                new_buttons = list(buttons)

            buttons = None
        else:
            if with_cancel or with_back:
                new_buttons = []
            else:
                new_buttons = None

        if with_cancel:
            self.add_cancel_button(ctx, new_buttons)
        if with_back:
            if not self._back_enabled:
                raise AttributeError(f'back is not enabled for this conversation ({self.__class__.__name__})')
            self.add_back_button(ctx, new_buttons)

        markup = ReplyKeyboardMarkup(new_buttons, one_time_keyboard=True) if new_buttons else IgnoreMarkup()
        ctx.reply(text, markup=markup)
        self.set_user_state(ctx.user_id, state)
        return state


class LangConversation(conversation):
    START, = range(1)

    @conventer(START, command='lang')
    def entry(self, ctx: Context):
        self._logger.debug(f'current language: {ctx.user_lang}')

        buttons = []
        for name in languages.values():
            buttons.append(name)
        markup = ReplyKeyboardMarkup([buttons, [ctx.lang('cancel')]], one_time_keyboard=False)

        ctx.reply(ctx.lang('select_language'), markup=markup)
        return self.START

    @convinput(START, messages=lang.languages)
    def input(self, ctx: Context):
        selected_lang = None
        for key, value in languages.items():
            if value == ctx.text:
                selected_lang = key
                break

        if selected_lang is None:
            raise ValueError('could not find the language')

        db.set_user_lang(ctx.user_id, selected_lang)
        ctx.reply(ctx.lang('saved'), markup=IgnoreMarkup())

        return self.END


def initialize():
    global _user_filter
    global _updater
    global _dispatcher

    # init user_filter
    if 'users' in config['bot']:
        _logger.info('allowed users: ' + str(config['bot']['users']))
        _user_filter = Filters.user(config['bot']['users'])
    else:
        _user_filter = Filters.all  # not sure if this is correct

    # init updater
    _updater = Updater(config['bot']['token'],
                       request_kwargs={'read_timeout': 6, 'connect_timeout': 7})

    # transparently log all messages
    _updater.dispatcher.add_handler(MessageHandler(Filters.all & _user_filter, _logging_message_handler), group=10)
    _updater.dispatcher.add_handler(CallbackQueryHandler(_logging_callback_handler), group=10)


def run(start_handler=None, any_handler=None):
    global db
    global _start_handler_ref

    if not start_handler:
        start_handler = _default_start_handler
    if not any_handler:
        any_handler = _default_any_handler
    if not db:
        db = BotDatabase()

    _start_handler_ref = start_handler

    _updater.dispatcher.add_handler(LangConversation().get_handler(), group=0)
    _updater.dispatcher.add_handler(CommandHandler('start', simplehandler(start_handler), _user_filter))
    _updater.dispatcher.add_handler(MessageHandler(Filters.all & _user_filter, any_handler))

    _updater.start_polling()
    _updater.idle()


def add_conversation(conv: conversation) -> None:
    _updater.dispatcher.add_handler(conv.get_handler(), group=0)


def add_handler(h):
    _updater.dispatcher.add_handler(h, group=0)


def start(ctx: Context):
    return _start_handler_ref(ctx)


def _default_start_handler(ctx: Context):
    if 'start_message' not in lang:
        return ctx.reply('Please define start_message or override start()')
    ctx.reply(ctx.lang('start_message'))


@simplehandler
def _default_any_handler(ctx: Context):
    if 'invalid_command' not in lang:
        return ctx.reply('Please define invalid_command or override any()')
    ctx.reply(ctx.lang('invalid_command'))


def _logging_message_handler(update: Update, context: CallbackContext):
    if _reporting:
        _reporting.report(update.message)


def _logging_callback_handler(update: Update, context: CallbackContext):
    if _reporting:
        _reporting.report(update.callback_query.message, text=update.callback_query.data)


def enable_logging(bot_type: BotType):
    api = WebAPIClient(timeout=3)
    api.enable_async()

    global _reporting
    _reporting = ReportingHelper(api, bot_type)


def notify_all(text_getter: callable,
               exclude: Tuple[int] = ()) -> None:
    if 'notify_users' not in config['bot']:
        _logger.error('notify_all() called but no notify_users directive found in the config')
        return

    for user_id in config['bot']['notify_users']:
        if user_id in exclude:
            continue

        text = text_getter(db.get_user_lang(user_id))
        _updater.bot.send_message(chat_id=user_id,
                                  text=text,
                                  parse_mode='HTML')


def notify_user(user_id: int, text: Union[str, Exception], **kwargs) -> None:
    if isinstance(text, Exception):
        text = exc2text(text)
    _updater.bot.send_message(chat_id=user_id,
                              text=text,
                              parse_mode='HTML',
                              **kwargs)


def send_photo(user_id, **kwargs):
    _updater.bot.send_photo(chat_id=user_id, **kwargs)


def send_audio(user_id, **kwargs):
    _updater.bot.send_audio(chat_id=user_id, **kwargs)


def send_file(user_id, **kwargs):
    _updater.bot.send_document(chat_id=user_id, **kwargs)


def edit_message_text(user_id, message_id, *args, **kwargs):
    _updater.bot.edit_message_text(chat_id=user_id,
                                   message_id=message_id,
                                   parse_mode='HTML',
                                   *args, **kwargs)


def delete_message(user_id, message_id):
    _updater.bot.delete_message(chat_id=user_id, message_id=message_id)


def set_database(_db: BotDatabase):
    global db
    db = _db

