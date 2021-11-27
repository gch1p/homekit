from telegram import User
from .lang import LangStrings

_strings = {
    'en': LangStrings(
        usage='Usage',
        arguments='Arguments'
    ),
    'ru': LangStrings(
        usage='Использование',
        arguments='Аргументы'
    )
}


def command_usage(command: str, arguments: dict, language='en') -> str:
    if language not in _strings:
        raise ValueError('unsupported language')

    blocks = []
    argument_names = []
    argument_lines = []
    for k, v in arguments.items():
        argument_names.append(k)
        argument_lines.append(
            f'<code>{k}</code>: {v}'
        )

    command = f'/{command}'
    if argument_names:
        command += ' ' + ' '.join(argument_names)

    blocks.append(
        f'<b>{_strings[language]["usage"]}</b>\n'
        f'<code>{command}</code>'
    )

    if argument_lines:
        blocks.append(
            f'<b>{_strings[language]["arguments"]}</b>\n' + '\n'.join(argument_lines)
        )

    return '\n\n'.join(blocks)


def user_any_name(user: User) -> str:
    name = [user.first_name, user.last_name]
    name = list(filter(lambda s: s is not None, name))
    name = ' '.join(name).strip()

    if not name:
        name = user.username

    if not name:
        name = str(user.id)

    return name
