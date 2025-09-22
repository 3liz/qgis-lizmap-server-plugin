

import os

from lizmap_server.tools import to_bool

GOOGLE_KEY = 'GOOGLE'
BING_KEY = 'BING'

GOOGLE_DOMAIN = 'google.com'
BING_DOMAIN = 'virtualearth.net'


def strict_tos_check_key(provider: str) -> str:
    """ Check the environment variable for this provider. """
    return f'STRICT_{provider}_TOS_CHECK'


def strict_tos_check(provider: str) -> bool:
    """ Check the environment variable for this provider. """
    return to_bool(os.getenv(strict_tos_check_key(provider), True))
