import logging

from typing import Optional, Dict, List, Union

_logger = logging.getLogger(__name__)


class LangStrings(dict):
    _lang: Optional[str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lang = None

    def setlang(self, lang: str):
        self._lang = lang

    def __missing__(self, key):
        _logger.warning(f'key {key} is missing in language {self._lang}')
        return '{%s}' % key

    def __setitem__(self, key, value):
        raise NotImplementedError(f'setting translation strings this way is prohibited (was trying to set {key}={value})')


class LangPack:
    strings: Dict[str, LangStrings[str, str]]
    default_lang: str

    def __init__(self):
        self.strings = {}
        self.default_lang = 'en'

    def ru(self, **kwargs) -> None:
        self.set(kwargs, 'ru')

    def en(self, **kwargs) -> None:
        self.set(kwargs, 'en')

    def set(self,
            strings: Union[LangStrings, dict],
            lang: str) -> None:

        if isinstance(strings, dict) and not isinstance(strings, LangStrings):
            strings = LangStrings(**strings)
            strings.setlang(lang)

        if lang not in self.strings:
            self.strings[lang] = strings
        else:
            self.strings[lang].update(strings)

    def all(self, key):
        result = []
        for strings in self.strings.values():
            result.append(strings[key])
        return result

    @property
    def languages(self) -> List[str]:
        return list(self.strings.keys())

    def get(self, key: str, lang: str, *args) -> str:
        if args:
            return self.strings[lang][key] % args
        else:
            return self.strings[lang][key]

    def __call__(self, *args, **kwargs):
        return self.strings[self.default_lang][args[0]]

    def __getitem__(self, key):
        return self.strings[self.default_lang][key]

    def __setitem__(self, key, value):
        raise NotImplementedError('setting translation strings this way is prohibited')

    def __contains__(self, key):
        return key in self.strings[self.default_lang]

    @staticmethod
    def pfx(prefix: str, l: list) -> list:
        return list(map(lambda s: f'{prefix}{s}', l))



languages = {
    'en': 'English',
    'ru': 'Русский'
}


lang = LangPack()
lang.en(
    en='English',
    ru='Russian',
    start_message="Select command on the keyboard.",
    unknown_message="Unknown message",
    cancel="🚫 Cancel",
    back='🔙 Back',
    select_language="Select language on the keyboard.",
    invalid_language="Invalid language. Please try again.",
    saved='Saved.',
    please_wait="⏳ Please wait..."
)
lang.ru(
    en='Английский',
    ru='Русский',
    start_message="Выберите команду на клавиатуре.",
    unknown_message="Неизвестная команда",
    cancel="🚫 Отмена",
    back='🔙 Назад',
    select_language="Выберите язык на клавиатуре.",
    invalid_language="Неверный язык. Пожалуйста, попробуйте снова",
    saved="Настройки сохранены.",
    please_wait="⏳ Ожидайте..."
)