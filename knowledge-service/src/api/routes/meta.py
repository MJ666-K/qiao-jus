from ingest.doc_types import DOC_TYPE_LABELS

from fastapi import APIRouter

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/doc-types")
async def doc_types():
    return [{"id": k, "label": v} for k, v in DOC_TYPE_LABELS.items()]
