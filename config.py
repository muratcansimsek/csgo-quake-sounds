import configparser
from threading import Lock, Thread

lock = Lock()
config = configparser.ConfigParser()
config.read('config.ini')

def saveCfg():
    with lock:
        with open('config.ini', 'w') as outfile:
            config.write(outfile, space_around_delimiters=True)

def set(section, option, val):
    with lock:
        config.set(section, option, str(val))
    Thread(target=saveCfg, daemon=False).start()
