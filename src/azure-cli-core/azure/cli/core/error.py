import re
from collections import namedtuple
from enum import Enum
from typing import Any, Callable, Dict, Pattern, Tuple, Union

from colorama import Fore, Style
from knack.log import get_logger

from azure.cli.core._error_handlers import (
    _handle_resource_not_found_error
)

logger = get_logger(__name__)

def _assert_parameter_is_of_correct_type(name: str, obj: Any, class_or_tuple: Union[type, Tuple[type]]):
    if not isinstance(obj, class_or_tuple):
        of_type_msg = f'of type {class_or_tuple.__name__}' if isinstance(class_or_tuple, type) else \
                      f'{" or ".join([_type.__name__ for _type in class_or_tuple])}'
        raise TypeError(f'expected {name} to be {of_type_msg}, got {type(obj).__name__}')

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]

ErrorType = namedtuple('ErrorType', ['error_type', 'pattern'])

class AzCliErrorType(Enum):
    ResourceNotFound = ErrorType(
        error_type='Resource not found',
        pattern=(
            r'(?P<azure_resource>[A-Za-z\s]+)\s+\'(?P<invalid_resource_name>.*)\'\s+(?:not found|could not be found)'
        )
    )

    def __init__(self, error_type: str, pattern: str):
        super().__init__()
        _assert_parameter_is_of_correct_type('error_type', error_type, str)
        _assert_parameter_is_of_correct_type('pattern', pattern, str)

        self._error_type: str = error_type
        self._pattern: Pattern[str] = re.compile(pattern)

    @property
    def error_type(self) -> str:
        return self._error_type

    @property
    def pattern(self) -> Pattern[str]:
        return self._pattern

    def __eq__(self, value: Union['AzCliErrorType', str]):
        if hasattr(value, 'value'):
            value = value.value
        # pylint: disable=comparison-with-callable
        return self.value == value

    def __hash__(self):
        return hash(self.value)

ErrorHandlerMapType = Dict[AzCliErrorType, Callable[[re.Match], Union[str, None]]]

class AzCliErrorHandler(metaclass=Singleton):
    ERROR_MSG_FMT_STR = f'{Style.BRIGHT}{Fore.RED}{{error_type}}{Style.NORMAL}: {{msg}}{Style.RESET_ALL}'

    def __init__(self):
        super().__init__()
        self._error_handlers: ErrorHandlerMapType = {
            AzCliErrorType.ResourceNotFound: _handle_resource_not_found_error
        }

    def __call__(self, error: Union[Exception, str]):
        message = error
        override = True
        cli_error_type: Union[AzCliErrorType, None] = None

        print('AzCliErrorHandler called with error {0}'.format(error))

        if isinstance(error, Exception):
            message = str(getattr(error, 'message', error))

        for cli_error_type, error_handler in self._error_handlers.items():
            if match := cli_error_type.pattern.search(message):
                if _error := error_handler(match):
                    message = _error
                    break
        else:
            override = False

        if override and cli_error_type:
            message = self.ERROR_MSG_FMT_STR.format(
                error_type=cli_error_type.error_type,
                msg=message
            )
            if isinstance(error, str):
                error = message
        return error

if __name__ == "__main__":
    print(AzCliErrorHandler()('Resource group \'newsampleUXgroup\' could not be found.'))
