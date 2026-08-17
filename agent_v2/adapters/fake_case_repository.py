"""Offline case repository fake for Member 2 contract tests."""


class FakeCaseRepository:
    def __init__(self, cases):
        self._cases = {case["exception_id"]: case for case in cases}

    def get_case(self, exception_id):
        return self._cases.get(exception_id)