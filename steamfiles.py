"""Parses steam ACF files.

Straight up ripped from https://github.com/leovp/steamfiles.
(I was having issues building with cx_Freeze)
"""


def loads(data, wrapper=dict):
    """
    Loads ACF content into a Python object.
    :param data: An UTF-8 encoded content of an ACF file.
    :param wrapper: A wrapping object for key-value pairs.
    :return: An Ordered Dictionary with ACF data.
    """
    if not isinstance(data, str):
        raise TypeError("can only load a str as an ACF but got " + type(data).__name__)

    parsed = wrapper()
    current_section = parsed
    sections = []

    lines = (line.strip() for line in data.splitlines())

    for line in lines:
        try:
            key, value = line.split(None, 1)
            key = key.replace('"', "").lstrip()
            value = value.replace('"', "").rstrip()
        except ValueError:
            if line == "{":
                # Initialize the last added section.
                current_section = _prepare_subsection(parsed, sections, wrapper)
            elif line == "}":
                # Remove the last section from the queue.
                sections.pop()
            else:
                # Add a new section to the queue.
                sections.append(line.replace('"', ""))
            continue

        current_section[key] = value

    return parsed


def load(fp, wrapper=dict):
    """
    Loads the contents of an ACF file into a Python object.
    :param fp: A file object.
    :param wrapper: A wrapping object for key-value pairs.
    :return: An Ordered Dictionary with ACF data.
    """
    return loads(fp.read(), wrapper=wrapper)


def _prepare_subsection(data, sections, wrapper):
    """
    Creates a subsection ready to be filled.
    :param data: Semi-parsed dictionary.
    :param sections: A list of sections.
    :param wrapper: A wrapping object for key-value pairs.
    :return: A newly created subsection.
    """
    current = data
    for i in sections[:-1]:
        current = current[i]

    current[sections[-1]] = wrapper()
    return current[sections[-1]]
