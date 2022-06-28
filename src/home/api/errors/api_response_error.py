from typing import Optional, List


class ApiResponseError(Exception):
    def __init__(self,
                 status_code: int,
                 error_type: str,
                 error_message: str,
                 error_stacktrace: Optional[List[str]] = None):
        super().__init__()
        self.status_code = status_code
        self.error_message = error_message
        self.error_type = error_type
        self.error_stacktrace = error_stacktrace

    def __str__(self):
        def st_formatter(line: str):
            return f'Remote| {line}'

        s = f'{self.error_type}: {self.error_message} (HTTP {self.status_code})'
        if self.error_stacktrace is not None:
            st = []
            for st_line in self.error_stacktrace:
                st.append('\n'.join(st_formatter(st_subline) for st_subline in st_line.split('\n')))
            s += '\nRemote stacktrace:\n'
            s += '\n'.join(st)

        return s
