### Building

The following commands are run using Python 3.6.7 - **it will *not* work in any other version**.

* Install [AVbin](https://github.com/AVbin/AVbin/downloads) and copy `avbin64.dll` (from system32) into the current directory

* Run the following :

* `pip install -r requirements.txt`

* `pip install git+git://github.com/leovp/steamfiles.git`

pynsist, pyinstaller, py2exe all fail at bundling for various reasons : we're using cxfreeze instead.

* `pip install cx_Freeze`

* Create an empty `__init__.py` in `site-packages/google` (yep...)

* Clear the `cache` directory

* Run `python setup.py build`
