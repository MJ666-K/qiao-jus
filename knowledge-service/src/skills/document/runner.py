from typing import Any

from pipeline.tasks import build_graph, chunk_and_embed, parse_document
from skills.base import Skill


class DocumentSkill(Skill):
    """文档处理 Skill

    处理文档上传、解析、切分、向量化、图谱构建的完整流程。
    """

    name = "document"
    description = "Document processing: upload, parse, chunk, embed, and build graph"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行文档处理

        Args:
            params: {
                "doc_id": str,          # 文档 ID
                "file_path": str,       # 文件路径
                "dataset_id": str,      # 数据集 ID
                "tenant_id": str,        # 租户 ID
                "action": str,           # 操作类型: upload, reindex
            }

        Returns:
            {
                "doc_id": str,
                "status": str,
                "message": str,
            }
        """
        action = params.get("action", "process")

        if action == "process":
            # 完整流水线: parse -> chunk+embed -> build_graph
            parse_result = parse_document.run(str(params["doc_id"]), str(params["file_path"]))
            chunk_result = chunk_and_embed.run(
                parse_result,
                str(params["doc_id"]),
                str(params["dataset_id"]),
                params["tenant_id"],
            )
            graph_result = build_graph.run(chunk_result, str(params["doc_id"]))
            return {
                "doc_id": params["doc_id"],
                "status": "done",
                "message": "Document processed successfully",
                "entities_count": len(graph_result.get("entities", [])),
            }

        elif action == "reindex":
            # 重新索引
            from pipeline.tasks import reindex_document

            reindex_document.delay(
                str(params["doc_id"]),
                str(params["file_path"]),
                str(params["dataset_id"]),
                params["tenant_id"],
            )
            return {
                "doc_id": params["doc_id"],
                "status": "queued",
                "message": "Reindexing started",
            }

        else:
            raise ValueError(f"Unknown action: {action}")
