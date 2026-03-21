# ============================================================================
# RUNNER ALURA - FastAPI
# ============================================================================

from fastapi import FastAPI

from projects.revisao_artigos.router import router as revisao_artigos_router

app = FastAPI()


@app.get("/ping")
def ping():
    return {"ok": True, "service": "runner"}


app.include_router(revisao_artigos_router)
