import traceback

from apig_http import responses


ROUTES = {}

def register(path, method='GET'):
    """Register a function as a route handler.

    >>> @register('/hello')
    ... def handle_hello(event, context):
    ...     return responses.HttpResponse('hi world!')
    >>> ROUTES['/hello']['GET']  #doctest: +ELLIPSIS
    <function handle_hello at ...>

    """
    def _inner(func):
        ROUTES.setdefault(path, {})[method] = func
        return func
    return _inner


def handle(event, context):
    """Process an incoming HTTP request from API Gateway.

    >>> event = {
    ...     'requestContext': {
    ...         'http': {
    ...              'path': '/hello',
    ...              'method': 'GET'
    ...         }
    ...     }
    ... }
    >>> handle(event, None)  #doctest: +ELLIPSIS
    <apig_http.responses.HttpResponse object at ...>

    """
    path = event['requestContext']['http']['path']
    method = event['requestContext']['http']['method']

    try:
        if path in ROUTES and method in ROUTES[path]:
            response = ROUTES[path][method](event, context)
        else:
            response = responses.HttpResponse('Not Found', 404)

    except Exception as ex:
        traceback.print_exc()
        response = responses.HttpResponse('Server error', 500)

    return response
