from urllib import parse


def trim_frag(url):
    """Trim off the fragment (#xyz) from a URL.

    >>> trim_frag('https://foo.bar/baz#quux')
    'https://foo.bar/baz'
    >>> trim_frag('')
    ''

    """
    return parse.urldefrag(url).url
