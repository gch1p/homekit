import re


def beautify_table(s):
    lines = s.split('\n')
    lines = list(map(lambda line: re.sub(r'\s+', ' ', line), lines))
    lines = list(map(lambda line: re.sub(r'(.*?): (.*)', r'<b>\1:</b> \2', line), lines))
    return '\n'.join(lines)
