"""Member 3 FastAPI wrapper with health, metrics and production settings."""

from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from integration.orchestrator import process_event

from member3.config import settings

import logging
try:
    import structlog
    structlog.configure()
except Exception:
    structlog = None

app = FastAPI()
logger = logging.getLogger("member3")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/api/orchestrate")
async def orchestrate(event: dict):
    """Accept the orchestrator `event` payload and return the orchestration result."""
    result = process_event(event)
    return result


if settings.ENABLE_PROMETHEUS:
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        @app.get("/metrics")
        async def metrics() -> Response:
            data = generate_latest()
            return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception:
        logger.warning("prometheus_client not installed; /metrics disabled")


@app.on_event("startup")
async def _startup_checks() -> None:
    # Try to verify Neo4j connectivity if driver is installed and env provided
    try:
        import neo4j

        uri = settings.NEO4J_URI
        user = settings.NEO4J_USER
        password = settings.NEO4J_PASSWORD
        try:
            driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            logger.info("Neo4j connectivity OK")
        except Exception as e:
            logger.warning("Neo4j connectivity check failed: %s", e)
    except Exception:
        logger.info("neo4j driver not installed; skipping connectivity check")


if __name__ == "__main__":
    import uvicorn

    host = settings.MEMBER3_HOST
    port = settings.MEMBER3_PORT
    uvicorn.run("member3_server:app", host=host, port=port)
