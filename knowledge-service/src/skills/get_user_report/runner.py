import uuid
from typing import Any

from sqlalchemy import select

from models.base import Report
from skills.base import Skill
from storage.postgres import SessionLocal


class GetUserReportSkill(Skill):
    name = "get_user_report"
    description = "Fetch a user's analysis report by report_id for report-bound Q&A"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        report_id = params.get("report_id")
        if not report_id:
            return {"report": None}
        async with SessionLocal() as session:
            res = await session.execute(
                select(Report).where(Report.id == uuid.UUID(report_id))
            )
            r = res.scalars().first()
            if not r:
                return {"report": None}
            return {
                "report": {
                    "id": str(r.id),
                    "type": r.type,
                    "summary": r.summary,
                    "risk_items": (r.content_json or {}).get("risk_items", []),
                    "citations": r.citations_json or [],
                    "suggested_questions": r.suggested_questions or [],
                    "confidence": r.confidence,
                }
            }
