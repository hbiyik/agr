'''
Created on Feb 6, 2024

@author: boogie
'''


class Cache:
    cache = {}

    @staticmethod
    def item(*args):
        keys = [str(x) for x in args]
        return "-".join(keys)

    @staticmethod
    def has(key, *args):
        item = Cache.item(*args)
        if key in Cache.cache and item in Cache.cache[key]:
            return Cache.cache[key][item]
        return False, None

    @staticmethod
    def make(key, retval, *args):
        item = Cache.item(*args)
        if key not in Cache.cache:
            Cache.cache[key] = {}
        Cache.cache[key][item] = True, retval

    @staticmethod
    def runonce(func):
        def decorated(*args, **kwargs):
            cachekey = func.__qualname__
            hascache, retval = Cache.has(cachekey, *args)
            if not hascache:
                retval = func(*args, **kwargs)
                Cache.make(cachekey, retval, *args)
            return retval
        return decorated
