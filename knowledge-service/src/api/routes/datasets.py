from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select

from api.deps import CurrentUserDep, SessionDep
from ingest.doc_types import SYSTEM_REPORT_DATASET
from models.base import Dataset, Document
from schemas.dataset import DatasetCreate, DatasetOut, DatasetUpdate

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
async def create_dataset(payload: DatasetCreate, user: CurrentUserDep, session: SessionDep):
    ds = Dataset(
        tenant_id=_uuid(user.tenant_id),
        name=payload.name,
        description=payload.description,
        acl=payload.acl,
        metadata_=payload.metadata,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return DatasetOut.model_validate(_as_out_dict(ds, 0))


@router.get("", response_model=list[DatasetOut])
async def list_datasets(user: CurrentUserDep, session: SessionDep):
    res = await session.execute(
        select(Dataset)
        .where(
            Dataset.tenant_id == _uuid(user.tenant_id),
            Dataset.name != SYSTEM_REPORT_DATASET,
        )
        .order_by(Dataset.created_at.desc())
    )
    datasets = res.scalars().all()
    if not datasets:
        return []

    ids = [d.id for d in datasets]
    count_res = await session.execute(
        select(Document.dataset_id, func.count())
        .join(Dataset, Document.dataset_id == Dataset.id)
        .where(
            Document.dataset_id.in_(ids),
            Dataset.name != SYSTEM_REPORT_DATASET,
            or_(
                Document.source_uri.is_(None),
                ~Document.source_uri.like("report://%"),
            ),
        )
        .group_by(Document.dataset_id)
    )
    counts = {str(ds_id): int(cnt) for ds_id, cnt in count_res.all()}
    return [
        DatasetOut.model_validate(_as_out_dict(d, counts.get(str(d.id), 0)))
        for d in datasets
    ]


@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset(dataset_id: str, user: CurrentUserDep, session: SessionDep):
    ds = await session.get(Dataset, _uuid(dataset_id))
    if not ds or str(ds.tenant_id) != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dataset not found")
    return DatasetOut.model_validate(_as_out_dict(ds, 0))


@router.patch("/{dataset_id}", response_model=DatasetOut)
async def update_dataset(
    dataset_id: str,
    payload: DatasetUpdate,
    user: CurrentUserDep,
    session: SessionDep,
):
    ds = await session.get(Dataset, _uuid(dataset_id))
    if not ds or str(ds.tenant_id) != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dataset not found")
    if payload.name is not None:
        ds.name = payload.name
    if payload.description is not None:
        ds.description = payload.description
    if payload.acl is not None:
        ds.acl = payload.acl
    await session.commit()
    await session.refresh(ds)
    return DatasetOut.model_validate(_as_out_dict(ds, 0))


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: str, user: CurrentUserDep, session: SessionDep):
    ds = await session.get(Dataset, _uuid(dataset_id))
    if not ds or str(ds.tenant_id) != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dataset not found")
    await session.delete(ds)
    await session.commit()


def _uuid(s: str):
    from uuid import UUID
    return UUID(s)


def _as_out_dict(ds: Dataset, document_count: int = 0) -> dict:
    return {
        "id": ds.id,
        "tenant_id": ds.tenant_id,
        "name": ds.name,
        "description": ds.description,
        "acl": ds.acl,
        "metadata": ds.metadata_,
        "created_at": ds.created_at,
        "document_count": document_count,
    }
