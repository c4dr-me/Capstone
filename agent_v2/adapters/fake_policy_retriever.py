"""Offline policy retriever fake for Member 2 contract tests."""


class FakePolicyRetriever:
    def retrieve(self, exception_type):
        return {"policy_id": "POL-TECH-001", "policy_version": "1.0", "citations": ("POL-TECH-001@1.0",)}