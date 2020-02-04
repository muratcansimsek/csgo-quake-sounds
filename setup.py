# -*- coding: utf-8 -*-
try:
    from setuptools import setup  # type: ignore
except ImportError:
    from distutils.core import setup

setup(
    name="csgo-custom-sounds",
    version="1.5.0",
    description="Play custom sounds via Gamestate Integration",
    python_requires="==3.*,>=3.7.0",
    author="kiwec",
    license="UNLICENSE",
    packages=[],
    package_dir={"": "."},
    package_data={},
    install_requires=[
        "aiofiles==0.*,>=0.4.0",
        "pyogg==0.6.11a1",
        "pyopenal==0.7.9a1",
        "wxasync==0.*,>=0.41.0",
    ],
)
