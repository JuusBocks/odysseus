"""Admin Danger Zone — per-category wipes.

Each endpoint is admin-only and truncates exactly one domain so the
user can selectively reset memory / skills / notes / etc. without
nuking everything. The catch-all `chats` endpoint mirrors the
existing /api/sessions/all so the Danger Zone speaks one URL pattern.

URL shape: DELETE /api/admin/wipe/{kind}
Kinds: chats, memory, skills, notes, tasks, documents, gallery, calendar.
"""

import json
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Request
import httpx

from core.middleware import require_admin
from core.database import (
    SessionLocal,
    ModelEndpoint,
    Session as DbSession,
    ChatMessage as DbChatMessage,
    Memory,
    Note,
    ScheduledTask,
    TaskRun,
    Document,
    DocumentVersion,
    GalleryImage,
    GalleryAlbum,
    CalendarEvent,
    CalendarCal,
)
from src.constants import (
    DATA_DIR,
    RUNTIME_STATUS_FILE,
    SKILLS_DIR,
    SKILLS_FILE,
    GALLERY_DIR,
    GALLERY_UPLOADS_DIR,
)

logger = logging.getLogger(__name__)

_LAUNCHD_LABEL = "com.leounib.projects.odysseus"
_STATUS_SKIP_DIRS = {
    "bg_jobs",
    "chroma",
    "fastembed_cache",
    "memory_vectors",
    "tts_cache",
}
_STATUS_EXTS = {".db", ".json", ".md", ".txt", ".ics", ".vcf", ".csv"}
_MODEL_WARM_KEEP_ALIVE = "30m"
_MODEL_WARM_AUTO_DELAY_SECONDS = 15
_MODEL_WARM_AUTO_MAX_PRIORITY = 21
_MODEL_WARM_LOCK = threading.Lock()
_MODEL_WARM_STATUS = {
    "queued": False,
    "running": False,
    "mode": "",
    "started_at": None,
    "finished_at": None,
    "current": "",
    "requested": [],
    "loaded": [],
    "results": [],
    "error": "",
}
_MODEL_WARM_PRIORITY = {
    "llama3.2:3b": 0,
    "qwen3:8b": 10,
    "deepseek-r1:8b": 11,
    "qwen3:14b": 20,
    "deepseek-r1:14b": 21,
    "qwen3:30b": 40,
    "deepseek-r1:32b": 41,
}


def _recommended_warm_models(models: list[str], leave_default_resident: bool = True) -> list[str]:
    recommended = [
        model for model in models
        if _MODEL_WARM_PRIORITY.get(model, 100) <= _MODEL_WARM_AUTO_MAX_PRIORITY
    ] or models[:1]
    if leave_default_resident and len(recommended) > 1:
        # Leave the smallest/default model resident after mid-tier warmup.
        recommended.append(recommended[0])
    return recommended


def _iso_from_epoch(ts: Optional[float]):
    if not ts:
        return None
    return datetime.fromtimestamp(ts).isoformat()


def _runtime_marker() -> dict:
    try:
        with open(RUNTIME_STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _last_data_write_at() -> str | None:
    latest = 0.0
    if not os.path.isdir(DATA_DIR):
        return None
    for root, dirs, files in os.walk(DATA_DIR):
        dirs[:] = [d for d in dirs if d not in _STATUS_SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext and ext not in _STATUS_EXTS:
                continue
            path = os.path.join(root, name)
            try:
                latest = max(latest, os.path.getmtime(path))
            except OSError:
                pass
    return _iso_from_epoch(latest)


def _running_background_jobs() -> list[dict]:
    try:
        from src import bg_jobs
        jobs = bg_jobs.refresh()
    except Exception as e:
        logger.warning("Could not refresh background jobs for runtime status: %s", e)
        return []
    running = []
    for rec in jobs.values():
        if rec.get("status") == "running":
            running.append({
                "type": "background_job",
                "id": rec.get("id"),
                "started_at": _iso_from_epoch(rec.get("started_at")),
            })
    return running


def _running_research_jobs(research_handler) -> list[dict]:
    if research_handler is None:
        return []
    running = []
    for sid, entry in getattr(research_handler, "_active_tasks", {}).items():
        if entry.get("status") == "running":
            running.append({
                "type": "research",
                "id": sid,
                "query": entry.get("query", ""),
                "started_at": _iso_from_epoch(entry.get("started_at")),
            })
    return running


def _ollama_root(base_url: str) -> str | None:
    parsed = urlparse((base_url or "").strip())
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return None
    port = parsed.port or 80
    if port != 11434:
        return None
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return f"{parsed.scheme or 'http'}://{parsed.netloc}{path}".rstrip("/")


def _json_list(value: str | None) -> list:
    try:
        data = json.loads(value or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _ollama_installed_models(root: str | None) -> list[str]:
    if not root:
        return []
    try:
        r = httpx.get(f"{root}/api/tags", timeout=5.0)
        r.raise_for_status()
        data = r.json()
        models = []
        for item in data.get("models", []):
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                models.append(name)
        return models
    except Exception as e:
        logger.warning("Could not read Ollama installed model list: %s", e)
        return []


def _local_ollama_warm_targets() -> tuple[str | None, list[str]]:
    db = SessionLocal()
    try:
        endpoints = (
            db.query(ModelEndpoint)
            .filter(ModelEndpoint.is_enabled == True)  # noqa: E712
            .order_by(ModelEndpoint.created_at)
            .all()
        )
        root = None
        models = []
        seen = set()
        for ep in endpoints:
            ep_root = _ollama_root(getattr(ep, "base_url", "") or "")
            if not ep_root:
                continue
            root = root or ep_root
            for model in _json_list(getattr(ep, "cached_models", None)):
                model = str(model or "").strip()
                if not model or model in seen:
                    continue
                seen.add(model)
                models.append(model)
        if root and not models:
            for model in _ollama_installed_models(root):
                if model not in seen:
                    seen.add(model)
                    models.append(model)
        models.sort(key=lambda m: (_MODEL_WARM_PRIORITY.get(m, 100), m))
        return root, models
    finally:
        db.close()


def _set_warm_status(**updates):
    with _MODEL_WARM_LOCK:
        _MODEL_WARM_STATUS.update(updates)


def _get_warm_status() -> dict:
    with _MODEL_WARM_LOCK:
        return json.loads(json.dumps(_MODEL_WARM_STATUS))


def _loaded_ollama_models(root: str | None) -> list[str]:
    if not root:
        return []
    try:
        r = httpx.get(f"{root}/api/ps", timeout=5.0)
        r.raise_for_status()
        data = r.json()
        return [
            str(item.get("name") or item.get("model") or "")
            for item in data.get("models", [])
            if item.get("name") or item.get("model")
        ]
    except Exception as e:
        logger.warning("Could not read Ollama loaded model list: %s", e)
        return []


def _warm_ollama_models(root: str, models: list[str], keep_alive: str):
    results = []
    _set_warm_status(
        queued=False,
        running=True,
        started_at=datetime.now().isoformat(),
        finished_at=None,
        current="",
        requested=models,
        loaded=[],
        results=[],
        error="",
    )
    timeout = httpx.Timeout(connect=5.0, read=300.0, write=10.0, pool=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            for model in models:
                _set_warm_status(current=model)
                started = time.time()
                try:
                    r = client.post(
                        f"{root}/api/generate",
                        json={
                            "model": model,
                            "prompt": "",
                            "stream": False,
                            "keep_alive": keep_alive,
                        },
                    )
                    elapsed = round(time.time() - started, 2)
                    if r.is_success:
                        results.append({"model": model, "ok": True, "seconds": elapsed})
                    else:
                        results.append({
                            "model": model,
                            "ok": False,
                            "seconds": elapsed,
                            "error": r.text[:240],
                        })
                except Exception as e:
                    results.append({
                        "model": model,
                        "ok": False,
                        "seconds": round(time.time() - started, 2),
                        "error": str(e),
                    })
                _set_warm_status(results=results[:], loaded=_loaded_ollama_models(root))
    except Exception as e:
        logger.exception("Model warmup failed")
        _set_warm_status(error=str(e))
    finally:
        _set_warm_status(
            queued=False,
            running=False,
            finished_at=datetime.now().isoformat(),
            current="",
            results=results[:],
            loaded=_loaded_ollama_models(root),
        )


def _start_model_warmup(delay_seconds: float = 0, mode: str = "recommended") -> dict:
    current = _get_warm_status()
    if current.get("running") or current.get("queued"):
        return current
    root, models = _local_ollama_warm_targets()
    if not root:
        raise HTTPException(400, "No local Ollama endpoint is enabled.")
    if not models:
        raise HTTPException(400, "No cached models found for the local Ollama endpoint.")
    if mode in {"auto", "recommended"}:
        models = _recommended_warm_models(models, leave_default_resident=True)

    _set_warm_status(
        queued=delay_seconds > 0,
        running=False,
        mode=mode,
        started_at=None,
        finished_at=None,
        current="",
        requested=models,
        loaded=_loaded_ollama_models(root),
        results=[],
        error="",
    )

    def _run():
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        current_status = _get_warm_status()
        if current_status.get("running") or current_status.get("mode") != mode:
            return
        _warm_ollama_models(root, models, _MODEL_WARM_KEEP_ALIVE)

    threading.Thread(target=_run, daemon=True).start()
    return {
        "queued": delay_seconds > 0,
        "running": delay_seconds <= 0,
        "mode": mode,
        "requested": models,
        "keep_alive": _MODEL_WARM_KEEP_ALIVE,
        "message": f"Loading {len(models)} local model(s).",
    }


def start_auto_model_warmup(delay_seconds: float = _MODEL_WARM_AUTO_DELAY_SECONDS) -> dict:
    """Queue local Ollama model warmup after startup without blocking app boot."""
    try:
        return _start_model_warmup(delay_seconds=delay_seconds, mode="auto")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Automatic model warmup could not be queued: %s", e)
        return {"queued": False, "running": False, "error": str(e)}


def _stop_odysseus_after_response():
    """Stop the launchd service after the HTTP response has gone out."""
    time.sleep(0.5)
    uid = os.getuid()
    target = f"gui/{uid}/{_LAUNCHD_LABEL}"
    try:
        subprocess.run(
            ["launchctl", "bootout", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return
    except Exception as e:
        logger.warning("launchctl bootout failed during shutdown request: %s", e)

    # Direct-dev fallback: stop this process if it was not launched by launchd.
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception as e:
        logger.warning("SIGTERM fallback failed during shutdown request: %s", e)


def _wipe_memory_files():
    """Blank memory.json + drop the per-owner tidy-state sidecar so the
    next audit doesn't try to diff against gone memories."""
    for name in ("memory.json", "memory_tidy_state.json"):
        p = os.path.join(DATA_DIR, name)
        if not os.path.exists(p):
            continue
        try:
            if name == "memory.json":
                with open(p, "w", encoding="utf-8") as f:
                    json.dump([], f)
            else:
                os.remove(p)
        except OSError as e:
            logger.warning(f"Could not reset {name}: {e}")


def _rmtree_quiet(path: str):
    """rmtree that doesn't crash if the path doesn't exist."""
    if os.path.isdir(path):
        try:
            shutil.rmtree(path)
        except OSError as e:
            logger.warning(f"Could not remove {path}: {e}")


def setup_admin_wipe_routes(session_manager, research_handler=None):
    """The session_manager is passed in so we can also clear its
    in-memory cache when wiping chats — without it the DB is empty
    but the next /api/sessions returns stale entries."""
    router = APIRouter(prefix="/api/admin")

    @router.post("/shutdown")
    def shutdown(request: Request):
        require_admin(request)
        threading.Thread(target=_stop_odysseus_after_response, daemon=True).start()
        return {"ok": True, "message": "Odysseus is shutting down."}

    @router.get("/runtime-status")
    def runtime_status(request: Request):
        require_admin(request)
        marker = _runtime_marker()
        active_work = _running_research_jobs(research_handler) + _running_background_jobs()
        last_export_at = marker.get("last_export_at")
        last_data_write_at = _last_data_write_at()
        safe_to_shutdown = len(active_work) == 0
        return {
            "safe_to_shutdown": safe_to_shutdown,
            "active_work_count": len(active_work),
            "active_work": active_work,
            "last_data_write_at": last_data_write_at,
            "last_export_at": last_export_at,
            "last_exported_by": marker.get("last_exported_by"),
            "message": "Ready to shut down" if safe_to_shutdown else "Active work is still running",
        }

    @router.get("/models/warm-status")
    def model_warm_status(request: Request):
        require_admin(request)
        status = _get_warm_status()
        root, models = _local_ollama_warm_targets()
        recommended = _recommended_warm_models(models, leave_default_resident=True)
        status["available"] = bool(root and models)
        status["configured_models"] = models
        status["recommended_models"] = recommended
        status["loaded"] = _loaded_ollama_models(root)
        status["keep_alive"] = _MODEL_WARM_KEEP_ALIVE
        return status

    @router.post("/models/warm")
    def warm_models(request: Request, full: bool = False):
        require_admin(request)
        return _start_model_warmup(delay_seconds=0, mode="full" if full else "recommended")

    @router.delete("/wipe/{kind}")
    def wipe(kind: str, request: Request):
        require_admin(request)
        kind = (kind or "").strip().lower()

        db = SessionLocal()
        try:
            if kind == "chats":
                count = db.query(DbSession).count()
                db.query(DbChatMessage).delete()
                db.query(DbSession).delete()
                db.commit()
                try:
                    session_manager.sessions.clear()
                except Exception:
                    pass
                return {"status": "deleted", "kind": kind, "count": count}

            if kind == "memory":
                count = db.query(Memory).count()
                db.query(Memory).delete()
                db.commit()
                _wipe_memory_files()
                # Drop the vector store too so semantic search doesn't
                # return ghosts. Lazy import — chromadb may not be
                # initialised in every deployment.
                try:
                    from src.memory_vector import get_memory_vector_store
                    mv = get_memory_vector_store()
                    if mv and hasattr(mv, "clear"):
                        mv.clear()
                except Exception as e:
                    logger.info(f"Memory vector clear skipped: {e}")
                return {"status": "deleted", "kind": kind, "count": count}

            if kind == "skills":
                # Skills live as SKILL.md files under data/skills/. Drop
                # the entire directory; the SkillsManager re-creates the
                # tree on next write.
                skills_dir = SKILLS_DIR
                count = 0
                if os.path.isdir(skills_dir):
                    # Count SKILL.md files for the response — quick walk.
                    for _, _, files in os.walk(skills_dir):
                        count += sum(1 for f in files if f == "SKILL.md")
                    _rmtree_quiet(skills_dir)
                # Legacy fallback file
                legacy = SKILLS_FILE
                if os.path.exists(legacy):
                    try:
                        os.remove(legacy)
                    except OSError:
                        pass
                return {"status": "deleted", "kind": kind, "count": count}

            if kind == "notes":
                count = db.query(Note).count()
                db.query(Note).delete()
                db.commit()
                return {"status": "deleted", "kind": kind, "count": count}

            if kind == "tasks":
                # TaskRun rows reference tasks via FK — clear them first.
                db.query(TaskRun).delete()
                count = db.query(ScheduledTask).count()
                db.query(ScheduledTask).delete()
                db.commit()
                return {"status": "deleted", "kind": kind, "count": count}

            if kind == "documents":
                # DocumentVersion FKs Document — clear children first.
                db.query(DocumentVersion).delete()
                count = db.query(Document).count()
                db.query(Document).delete()
                db.commit()
                return {"status": "deleted", "kind": kind, "count": count}

            if kind == "gallery":
                count = db.query(GalleryImage).count() + db.query(GalleryAlbum).count()
                db.query(GalleryImage).delete()
                db.query(GalleryAlbum).delete()
                db.commit()
                # Also drop the upload dir so disk doesn't keep orphans.
                _rmtree_quiet(GALLERY_DIR)
                _rmtree_quiet(GALLERY_UPLOADS_DIR)
                return {"status": "deleted", "kind": kind, "count": count}

            if kind == "calendar":
                # Events FK calendars — clear children first, then both.
                db.query(CalendarEvent).delete()
                count = db.query(CalendarCal).count()
                db.query(CalendarCal).delete()
                db.commit()
                return {"status": "deleted", "kind": kind, "count": count}

            raise HTTPException(400, f"Unknown wipe kind: {kind!r}")
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.exception(f"Wipe {kind} failed")
            raise HTTPException(500, f"Wipe {kind} failed: {e}")
        finally:
            db.close()

    return router
