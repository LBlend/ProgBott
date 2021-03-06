import codecs
import json
from collections import namedtuple


class Settings:
    def __init__(self, data_dir):
        self._data_dir = data_dir
        self._setting_path = self._data_dir + "/settings.json"
        self.default_prefix = "^"

        with codecs.open(self._setting_path, "r", encoding="utf8") as f:
            _json = json.load(f)
            self.token = _json["token"]
            self.prefix = _json["prefixes"]

            try:
                self.extra = namedtuple("settings", _json["extra"].keys())(*_json["extra"].values())
            except KeyError:
                pass
