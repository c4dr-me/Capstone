"""Start Member 3 server with governance env vars set for local Neo4j dev.

This script sets required env vars and runs the existing FastAPI wrapper.
"""
import os
import uvicorn

os.environ.setdefault("NEO4J_URI", os.environ.get("NEO4J_URI", "neo4j://localhost:7687"))
os.environ.setdefault("NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j"))
os.environ.setdefault("NEO4J_PASSWORD", os.environ.get("NEO4J_PASSWORD", "test"))
os.environ.setdefault("NEO4J_DATABASE", os.environ.get("NEO4J_DATABASE", "neo4j"))
os.environ.setdefault("RESOLVEONE_CONTEXT_SIGNING_KEY", os.environ.get("RESOLVEONE_CONTEXT_SIGNING_KEY", "demo-context-key"))
os.environ.setdefault("RESOLVEONE_RECEIPT_SIGNING_KEY", os.environ.get("RESOLVEONE_RECEIPT_SIGNING_KEY", "demo-receipt-key"))

if __name__ == "__main__":
    uvicorn.run("member3_server:app", host="0.0.0.0", port=8000)
