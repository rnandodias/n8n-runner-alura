# ============================================================================
# RUNNER ALURA - FastAPI
# ============================================================================

import os
import subprocess
import tempfile
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from projects.alura_utils.router import router as alura_utils_router
from projects.classificador_competencias.router import router as classificador_competencias_router
from projects.classificador_competencias.router_otimizado import router as classificador_otimizado_router
from projects.classificador_competencias.batch.router import router as classificador_batch_router
from projects.revisao_artigos.router import router as revisao_artigos_router

app = FastAPI()


@app.get("/ping")
def ping():
    return {"ok": True, "service": "runner"}


@app.get("/backup")
def backup():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL não configurada")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"runner_{timestamp}.sql.gz"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sql.gz")
    tmp_path = tmp.name
    tmp.close()

    print(f"[backup] iniciando dump → {filename}", flush=True)
    try:
        with open(tmp_path, "wb") as out:
            pg_dump = subprocess.Popen(
                ["pg_dump", "--no-owner", "--no-acl", "--dbname", db_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            gzip_proc = subprocess.Popen(["gzip", "-9"], stdin=pg_dump.stdout, stdout=out)
            pg_dump.stdout.close()
            gzip_proc.wait()
            pg_dump.wait()

            if pg_dump.returncode != 0:
                err = pg_dump.stderr.read().decode(errors="replace")
                raise HTTPException(status_code=500, detail=f"pg_dump falhou: {err}")

        size = os.path.getsize(tmp_path)
        print(f"[backup] dump pronto — {size / 1024 / 1024:.1f} MB", flush=True)
        return FileResponse(
            tmp_path,
            media_type="application/gzip",
            filename=filename,
            background=BackgroundTask(os.unlink, tmp_path),
        )
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


app.include_router(revisao_artigos_router)
app.include_router(alura_utils_router)
app.include_router(classificador_competencias_router)
app.include_router(classificador_otimizado_router)
app.include_router(classificador_batch_router)
