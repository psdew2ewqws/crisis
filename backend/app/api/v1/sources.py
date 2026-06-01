from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceRegister(BaseModel):
    id: str
    name: str
    type: str
    config: dict = {}


@router.get("")
async def list_sources(request: Request):
    repos = request.app.state.repos
    return repos.sources.list_all()


@router.post("")
async def register_source(body: SourceRegister, request: Request):
    repos = request.app.state.repos
    source = {
        "id": body.id, "name": body.name, "type": body.type,
        "config": body.config, "status": "registered",
    }
    repos.sources.save(body.id, source)
    return source


@router.post("/{source_id}/activate")
async def activate_source(source_id: str, request: Request):
    repos = request.app.state.repos
    source = repos.sources.get(source_id)
    if not source:
        raise HTTPException(404, f"Source {source_id} not found")
    source["status"] = "active"
    repos.sources.save(source_id, source)
    return source


@router.delete("/{source_id}")
async def delete_source(source_id: str, request: Request):
    repos = request.app.state.repos
    repos.sources.delete(source_id)
    return {"status": "deleted"}
