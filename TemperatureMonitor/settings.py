
DEBUG = False

USER = 'pi'
PASSWORD = 'raspberry'
TARGET_HOST = 'https://www.ipa-api.com'

MAX_TEMP_F = 68  # Degrees Fahrenheit

try:
    from local_settings import *
except ImportError:
    pass
