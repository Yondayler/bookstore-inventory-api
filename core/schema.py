"""OpenAPI schema post-processing."""


def strip_trailing_slashes(result, generator, request, public, **kwargs):
    """Document `/books` instead of `/books/`.

    The router accepts both forms, but the specification of this project uses
    the slash-less variant, so that is what the docs should advertise.
    """
    paths = result.get("paths")
    if not paths:
        return result

    rewritten = {}
    for path, definition in paths.items():
        normalized = path.rstrip("/") or "/"
        # Never let two different paths collapse onto each other.
        rewritten[normalized if normalized not in rewritten else path] = definition
    result["paths"] = rewritten
    return result
