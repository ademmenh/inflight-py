class InFlightConflictError(Exception):
    def __init__(self, query_key: str) -> None:
        self.query_key = query_key
        super().__init__(f'inflight conflict for "{query_key}"')
