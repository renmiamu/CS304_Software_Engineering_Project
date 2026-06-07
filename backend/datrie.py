class Trie:
    def __init__(self, alphabet=None):
        self._data = {}
        self._prefixes = set()

    @classmethod
    def load(cls, filename):
        raise ValueError("Native datrie cache is not supported by the local fallback")

    def save(self, filename):
        return None

    def __contains__(self, key):
        return key in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value
        for i in range(1, len(key) + 1):
            self._prefixes.add(key[:i])

    def has_keys_with_prefix(self, prefix):
        return prefix in self._prefixes
