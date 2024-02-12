'''
Created on Feb 6, 2024

@author: boogie
'''


class Cache:
    cache = {}

    @staticmethod
    def item(*args, **kwargs):
        keys = [str(x) for x in args]
        for k in sorted(kwargs):
            keys.append(f"{k}={kwargs[k]}")
        return "-".join(keys)

    @staticmethod
    def has(key, *args, **kwargs):
        item = Cache.item(*args, **kwargs)
        if key in Cache.cache and item in Cache.cache[key]:
            return Cache.cache[key][item]
        return False, None

    @staticmethod
    def make(key, retval, *args, **kwargs):
        item = Cache.item(*args, **kwargs)
        if key not in Cache.cache:
            Cache.cache[key] = {}
        Cache.cache[key][item] = True, retval

    @staticmethod
    def runonce(func):
        def decorated(*args, **kwargs):
            cachekey = func.__name__
            hascache, retval = Cache.has(cachekey, *args, **kwargs)
            if not hascache:
                retval = func(*args, **kwargs)
                Cache.make(cachekey, retval, *args, **kwargs)
            return retval
        return decorated
