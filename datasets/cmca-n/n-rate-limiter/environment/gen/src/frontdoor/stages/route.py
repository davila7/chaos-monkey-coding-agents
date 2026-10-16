"""Stage 1: find the route. 404 when no route matches, 405 when the route does not take the method."""

from frontdoor.routing.table import match

NAME = "route"


def setup(config):
    return None


def handle(ctx, state):
    r = match(ctx.config.routes, ctx.request.path)
    if r is None:
        return 404
    ctx.route = r
    if ctx.request.method not in r.methods:
        ctx.headers["Allow"] = ", ".join(r.methods)
        return 405
    return None
