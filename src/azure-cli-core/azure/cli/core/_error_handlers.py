# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import re

def _handle_resource_not_found_error(match: re.Match):
    invalid_resource_name = match.group('invalid_resource_name')
    return f'{invalid_resource_name} does not exist'
