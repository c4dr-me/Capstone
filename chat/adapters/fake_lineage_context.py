"""Fixture-backed read-only lineage context for standalone chat development."""


class FakeLineageContext:
    def get_context(self, exception_id):
        return {"exception_id": exception_id, "nodes": (), "edges": ()}