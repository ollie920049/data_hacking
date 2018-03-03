import asyncio
import socket
import json

from aiohttp import web
from functools import lru_cache

from dga import DGA


@lru_cache(maxsize=None)
def predict(host):
    return dga.evaluate_url(host)


async def apply(request):
    h = request.rel_url.query['host']
    return web.Response(text=json.dumps({
        'dga': predict(h)
    }))


if __name__ == "__main__":
    dga = DGA()

    # Find empty high socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()

    with open("endpoint.dat", "w") as text_file:
        text_file.write("{\"url\" : \"http://0.0.0.0:%d\"}" % port)

    app = web.Application()
    app.router.add_get('/apply', apply)
    web.run_app(app, port=port)

