try:
    # pip<=9.x.x
    from pip.utils.appdirs import user_cache_dir
except:
    # pip>=10.0.0
    from pip._internal.utils.appdirs import user_cache_dir

# The user_cache_dir helper comes straight from pip itself
CACHE_DIR = user_cache_dir('prequ')
