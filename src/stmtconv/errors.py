"""Operator-safe errors: callers must not include client data in messages."""


class StmtconvError(Exception):
    def __init__(self, code: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


class ConfigurationError(StmtconvError):
    pass


class SetupError(StmtconvError):
    pass


class OrderStateError(StmtconvError):
    pass
