# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import re
from enum import Enum, auto
from typing import Pattern, Set, Tuple, Union

class CorrectionType(Enum):
    InvalidArgument = auto()

class SuggestedErrorCorrection():
    VALUE_TYPE_TO_PARAMETER_NAME = {
        'resource_group_name': '--resource-group'
    }

    def __init__(self, suggestion: str, correction_type: CorrectionType, parameter: Union[str, None] = None):
        super().__init__()
        self.suggestion = suggestion
        self.parameter = self.VALUE_TYPE_TO_PARAMETER_NAME.get(parameter) or parameter
        self.correction_type = correction_type

    def __repr__(self):
        return (f'SuggestedErrorCorrection(suggestion={repr(self.suggestion)}'
                f', correction_type={str(self.correction_type)}'
                f', parameter={repr(self.parameter)})')

def _handle_resource_not_found_error(match: re.Match, _error_msg: str) -> str:
    invalid_resource_name = match.group('invalid_resource_name')
    return f'{invalid_resource_name} does not exist'

def _handle_character_not_allowed_error(match: re.Match, ex: Exception) -> Tuple[str, SuggestedErrorCorrection]:
    regex: str = match.group('regex')
    parameter: str = match.group('parameter')
    # fix the invalid regular expression output by the CLI
    regex = regex.replace(r'\\w', r'\\\w')

    # don't anchor the regular expression
    if regex.startswith('^'):
        regex = regex[1:]
    if regex.endswith('$'):
        regex = regex[:-1]

    pattern: Pattern[str] = re.compile(regex)

    invalid_value: str = getattr(ex, '_invalid_value', '')

    valid_value: str = invalid_value
    invalid_character_string: str = invalid_value
    valid_substrings = re.findall(pattern, invalid_value)
    invalid_character_set: Set[str] = set()

    for valid_substring in valid_substrings:
        invalid_character_string = invalid_character_string.replace(valid_substring, '')

    invalid_character_set = set(c for c in invalid_character_string)

    for invalid_character in invalid_character_set:
        valid_value = valid_value.replace(invalid_character, '')

    msg = ''.join(invalid_character_set)
    suggested_fix = SuggestedErrorCorrection(valid_value, CorrectionType.InvalidArgument, parameter=parameter)
    return msg, suggested_fix

ARGUMENT_PATTERN: Pattern[str] = re.compile(r'(?<!/)--(?P<argument>[a-z][A-Za-z-]*)')

def _handle_argument_required_error(_match: re.Match, error_msg: str):
    buffer = []

    if arguments := re.findall(ARGUMENT_PATTERN, error_msg):
        for i, arg in enumerate(arguments):
            arg = arg
            if i == 0:
                buffer.append(arg)
            else:
                buffer.append(f' and {arg}')

    msg = ''.join(buffer)
    return msg

def _handle_value_required_error(_match: re.Match, error_msg: str):
    msg = None

    if argument := ARGUMENT_PATTERN.search(error_msg):
        msg = argument.group()

    return msg

def _handle_command_not_found_error(match: re.Match, _error_msg: str):
    subcommand: str = match.group('subcommand')
    command_group: str = match.group('command_group')
    return f'{command_group} {subcommand}'
