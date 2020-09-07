import re
from collections import namedtuple
from enum import Enum
from typing import Any, Callable, Dict, Pattern, Tuple, Union

from colorama import Fore, Style
from knack.log import get_logger

from azure.cli.core._error_handlers import (
    SuggestedErrorCorrection,
    _handle_resource_not_found_error,
    _handle_character_not_allowed_error,
    _handle_command_not_found_error,
    _handle_argument_required_error,
    _handle_value_required_error
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
    ArgumentRequired = ErrorType(
        error_type='Argument required',
        pattern=(
            r'the following arguments are required'
        )
    )
    CharacterNotAllowed = ErrorType(
        error_type='Character not allowed',
        pattern=(
            r'[Pp]arameter\s+\'(?P<parameter>.*)\'\s+.*pattern[:\s]+\'(?P<regex>.*)\''
        )
    )
    CommandNotFound = ErrorType(
        error_type='Command not found',
        pattern=(
            r'([\'\"])(?P<subcommand>.*)\1 is not in the \1(?P<command_group>az\s.*)\1 command group'
        )
    )
    ResourceNotFound = ErrorType(
        error_type='Resource not found',
        pattern=(
            r'(?P<azure_resource>[A-Za-z\s]+)\s+\'(?P<invalid_resource_name>.*)\'\s+(?:not found|could not be found)'
        )
    )
    ValueRequired = ErrorType(
        error_type='Value Required',
        pattern=(
            r'expected (at least)?\s?one argument'
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

ErrorHandlerMapType = Dict[AzCliErrorType, Callable[[re.Match], Union[str, Tuple[str, SuggestedErrorCorrection], None]]]

class AzCliError():
    def __init__(self,
                 message: str,
                 overridden_message: str,
                 suggested_fix: SuggestedErrorCorrection,
                 cli_error_type: AzCliErrorType,
                 metadata: re.Match):

        super().__init__()
        self.message = message
        self.overridden_message = overridden_message
        self.suggested_fix = suggested_fix
        self.cli_error_type = cli_error_type
        self.metadata = metadata

    def __repr__(self):
        return (f'AzCliError(message={repr(self.message)}'
                f', overridden_message={repr(self.overridden_message)})'
                f', suggested_fix={repr(self.suggested_fix)})'
                f', cli_error_type={repr(self.cli_error_type)}'
                f', metadata={repr(self.metadata)})')

class AzCliErrorHandler(metaclass=Singleton):
    ERROR_MSG_FMT_STR = f'{Style.BRIGHT}{Fore.RED}{{error_type}}{Style.NORMAL}: {{msg}}{Style.RESET_ALL}'

    def __init__(self):
        super().__init__()
        self._last_error: Union[AzCliError, None] = None
        self._error_handlers: ErrorHandlerMapType = {
            AzCliErrorType.ResourceNotFound: _handle_resource_not_found_error,
            AzCliErrorType.CharacterNotAllowed: _handle_character_not_allowed_error,
            AzCliErrorType.CommandNotFound: _handle_command_not_found_error,
            AzCliErrorType.ArgumentRequired: _handle_argument_required_error,
            AzCliErrorType.ValueRequired: _handle_value_required_error,
        }

    def get_last_error(self):
        return self._last_error

    def __call__(self, error: Union[Exception, str], *args, **kwargs):
        logger.debug('AzCliErrorHandler called on error: %(error)s', {'error': error})

        message = error
        match: Union[re.Match, None] = None
        suggested_fix: Union[SuggestedErrorCorrection, None] = None
        override = True
        cli_error_type: Union[AzCliErrorType, None] = None

        _assert_parameter_is_of_correct_type('error', error, (str, Exception))

        if isinstance(error, Exception):
            message = str(getattr(error, 'message', error))

        overridden_message: str = message

        for cli_error_type, error_handler in self._error_handlers.items():
            if match := cli_error_type.pattern.search(message):
                if result := error_handler(match, error, *args, **kwargs):
                    if isinstance(result, tuple) and len(result) == 2:
                        message, suggested_fix = result
                    else:
                        message = result

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
            elif isinstance(error, Exception):
                setattr(error, 'message', message)
                setattr(error, 'args', [message, *getattr(error, 'args', [])[1:]])

            self._last_error = AzCliError(
                message=message,
                overridden_message=overridden_message,
                suggested_fix=suggested_fix,
                cli_error_type=cli_error_type,
                metadata=match
            )

        return error

if __name__ == "__main__":
    from msrest.exceptions import ValidationError
    ex = Exception("""validation error: Parameter 'resource_group_name' must conform to the following pattern: '^[-\\w\\._\\(\\)]+$'.""")
    setattr(ex, '_invalid_value', 'sampleUX!!group')
    print(AzCliErrorHandler()('Resource group \'newsampleUXgroup\' could not be found.'))
    print(AzCliErrorHandler()('az storage: "create" is not in the "az storage" command group'))
    print(AzCliErrorHandler()('az storage account create: error: the following arguments are required: --resource-group/-g, --name/-n'))
    print(AzCliErrorHandler()('az storage container create: error: argument --connection-string: expected one argument'))
    print(AzCliErrorHandler()('az group delete: error: the following arguments are required: --name/-n/--resource-group/-g'))
    print(AzCliErrorHandler()('az vm nic show: error: the following arguments are required: --vm-name, --nic'))
    print(AzCliErrorHandler()(ex))
    print(AzCliErrorHandler().get_last_error())