"""Document type constants aligned with 枫桥智诉 platform KB design."""

LAW = "law"
CASE = "case"
COMPLIANCE = "compliance"
CONTRACT = "contract"
DISPUTE = "dispute"
REPORT = "report"
GENERAL = "general"

PLATFORM_TYPES = {LAW, CASE, COMPLIANCE}
USER_TYPES = {CONTRACT, DISPUTE, REPORT}

DOC_TYPE_LABELS = {
    LAW: "法律法规",
    CASE: "裁判文书/类案",
    COMPLIANCE: "合规条款",
    CONTRACT: "合同",
    DISPUTE: "纠纷材料",
    REPORT: "分析报告",
    GENERAL: "通用文档",
}

# Chunk params from docs/技术架构文档.md + docs/对话参考.txt
CHUNK_PARAMS = {
    LAW: {"mode": "article", "max_chars": 800, "overlap": 0},
    CASE: {"mode": "sliding", "max_chars": 512, "overlap": 64},
    COMPLIANCE: {"mode": "sliding", "max_chars": 256, "overlap": 32},
    GENERAL: {"mode": "parent_child", "parent_tokens": 1200, "child_tokens": 300, "overlap": 50},
}
