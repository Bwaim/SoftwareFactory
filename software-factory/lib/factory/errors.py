class FactoryError(Exception):
    pass


class ExistsError(FactoryError):
    pass


class DetailedError(FactoryError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details
