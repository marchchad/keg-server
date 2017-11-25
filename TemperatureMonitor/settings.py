
DEBUG = False

USER = 'pi'
PASSWORD = 'raspberry'
TARGET_HOST = 'https://www.ipa-api.com'


try:
    from local_settings import *
except ImportError:
    pass
