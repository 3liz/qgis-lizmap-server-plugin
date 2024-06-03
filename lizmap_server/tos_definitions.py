__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

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
    env = os.getenv(strict_tos_check_key(provider))
    if env is None:
        env = True
    return to_bool(env)
