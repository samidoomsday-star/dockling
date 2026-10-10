"""Safe server errors contain codes, never raw provider/database input."""


class WebError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(code)


def missing() -> WebError:
    return WebError(404, "NOT_FOUND", "This resource is unavailable.")
