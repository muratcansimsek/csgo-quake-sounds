import configparser

config = configparser.ConfigParser()
config.read("config.ini")


def saveCfg():
    with open("config.ini", "w") as outfile:
        config.write(outfile, space_around_delimiters=True)


def set(section, option, val):
    config.set(section, option, str(val))
    saveCfg()
