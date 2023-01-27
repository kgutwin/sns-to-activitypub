import json


class HttpResponse:
    """Represents the HTTP response of a route method.

    An empty body will result in a 204 No Content reply.

    >>> HttpResponse().to_http()  #doctest: +NORMALIZE_WHITESPACE
    {'statusCode': 204, 'statusDescription': 'No Content', 'body': '', 
     'headers': {}}

    A string body will be returned as 200 OK.

    >>> HttpResponse('hello world').to_http()  #doctest: +NORMALIZE_WHITESPACE
    {'statusCode': 200, 'statusDescription': 'OK', 'body': 'hello world',
     'headers': {}}

    A dict body will be converted to JSON and the content-type set
    appropriately.

    >>> HttpResponse({'he': 'llo'}).to_http() #doctest: +NORMALIZE_WHITESPACE
    {'statusCode': 200, 'statusDescription': 'OK', 'body': '{"he": "llo"}',
     'headers': {'Content-Type': 'application/jrd+json'}}

    A different status code can be returned as well.

    >>> HttpResponse(status_code=401).to_http() #doctest: +NORMALIZE_WHITESPACE
    {'statusCode': 401, 'statusDescription': 'Unauthorized', 'body': '',
     'headers': {}}

    """
    def __init__(self, body='', status_code=200):
        self.headers = {}
        self.status_code = status_code
        
        if isinstance(body, dict):
            self.body = json.dumps(body)
            self.headers['Content-Type'] = 'application/jrd+json'
        else:
            self.body = body
        
    def to_http(self):
        if not self.body and self.status_code == 200:
            self.body = ''
            self.status_code = 204
            
        return {
            'statusCode': self.status_code,
            'statusDescription': {
                200: 'OK',
                204: 'No Content',
                401: 'Unauthorized',
                403: 'Forbidden',
                404: 'Not Found',
                500: 'Server error',
            }.get(self.status_code, 'Unsure'),
            'body': self.body,
            'headers': self.headers,
        }

    
