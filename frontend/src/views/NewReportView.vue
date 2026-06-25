<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { listAllDocuments } from "@/api/documents";
import { docTypeLabel, isUserUploadedDoc } from "@/constants/docTypes";
import { useReportsStore } from "@/stores/reports";
import type { DocumentItem, ReportType } from "@/types";

type ModuleKey = "m1" | "m2" | "m3" | "m4" | "m5";

interface ModuleSpec {
  key: ModuleKey;
  label: string;
  desc: string;
  report_type: ReportType;
  mode: "doc" | "text";
  doc_type?: string;
  text_placeholder: string;
  text_default?: string;
}

const MODULES: ModuleSpec[] = [
  {
    key: "m1",
    label: "M1 纠纷研判",
    desc: "上传纠纷材料（事实、证据），生成纠纷研判报告：案由、证据清单、调解建议",
    report_type: "dispute_analysis",
    mode: "doc",
    doc_type: "dispute",
    text_placeholder: "或直接粘贴纠纷描述（无需上传文件）",
  },
  {
    key: "m2",
    label: "M2 合同审查",
    desc: "上传合同 PDF，自动识别风险条款（试用期/违约金/管辖等），生成审查报告",
    report_type: "contract_review",
    mode: "doc",
    doc_type: "contract",
    text_placeholder: "或直接粘贴合同条款文本",
  },
  {
    key: "m3",
    label: "M3 用工风险排查",
    desc: "粘贴用工合同或描述用工情形，规则引擎 + 法规库生成劳动用工风险报告",
    report_type: "labor_risk",
    mode: "text",
    text_placeholder:
      "粘贴劳动合同条款或用工情形描述。例如：约定试用期一年，加班无加班费，未缴纳社保...",
  },
  {
    key: "m4",
    label: "M4 诉讼文书生成",
    desc: "输入案由与事实，生成起诉状 / 答辩状草稿",
    report_type: "litigation_draft",
    mode: "text",
    text_placeholder:
      "描述案由与事实。例如：案由：物业服务合同纠纷。事实：原告入住后物业不履行维修义务...",
  },
  {
    key: "m5",
    label: "M5 证据清单指引",
    desc: "选择案由，输出该类纠纷需要的证据清单 + 举证流程",
    report_type: "evidence_checklist",
    mode: "text",
    text_placeholder:
      "输入案由（如：物业纠纷、借贷纠纷、劳动争议），生成证据清单",
  },
];

const PLATFORM_DOC_TYPES = new Set(["law", "case", "compliance"]);

const router = useRouter();
const store = useReportsStore();

const activeKey = ref<ModuleKey>("m1");
const documents = ref<DocumentItem[]>([]);
const loadingDocs = ref(false);
const selectedDocIds = ref<string[]>([]);
const textInput = ref<string>("");
const submitting = ref(false);

const activeModule = computed(
  () => MODULES.find((m) => m.key === activeKey.value) as ModuleSpec,
);

function docTypeOf(d: DocumentItem): string {
  return String(d.metadata?.doc_type || "general");
}

function isSelectableDocument(d: DocumentItem): boolean {
  return d.status === "done" && isUserUploadedDoc(d) && !PLATFORM_DOC_TYPES.has(docTypeOf(d));
}

function docOptionLabel(d: DocumentItem): string {
  const typeLabel = docTypeLabel(docTypeOf(d));
  return typeLabel === "未知" ? d.title : `${d.title} · ${typeLabel}`;
}

async function loadDocuments() {
  loadingDocs.value = true;
  try {
    const all = await listAllDocuments({ status_filter: "done", uploaded_only: true });
    const primary = activeModule.value.doc_type;
    documents.value = all
      .filter(isSelectableDocument)
      .sort((a, b) => {
        const rank = (d: DocumentItem) => {
          const dt = docTypeOf(d);
          if (dt === primary) return 0;
          if (dt === "general" || dt === "report") return 1;
          return 2;
        };
        return rank(a) - rank(b);
      });
  } catch (e) {
    documents.value = [];
    ElMessage.error(e instanceof Error ? e.message : "加载文档列表失败");
  } finally {
    loadingDocs.value = false;
  }
}

function switchModule(key: ModuleKey) {
  activeKey.value = key;
  selectedDocIds.value = [];
  textInput.value = activeModule.value.text_default || "";
  if (activeModule.value.mode === "doc") {
    loadDocuments();
  }
}

async function submit() {
  if (
    activeModule.value.mode === "doc" &&
    !selectedDocIds.value.length &&
    !textInput.value.trim()
  ) {
    ElMessage.warning("请选择已上传文档，或直接输入文本");
    return;
  }
  if (activeModule.value.mode === "text" && !textInput.value.trim()) {
    ElMessage.warning("请输入文本内容");
    return;
  }

  submitting.value = true;
  try {
    if (!selectedDocIds.value.length && textInput.value.trim()) {
      await triggerViaText();
      return;
    }
    await store.triggerAnalyze(
      selectedDocIds.value,
      activeModule.value.report_type,
    );
    ElMessage.success("报告已开始生成");
    router.push({ name: "reports-list" });
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "触发分析失败");
  } finally {
    submitting.value = false;
  }
}

async function triggerViaText() {
  const { analyzeReport } = await import("@/api/reports");
  try {
    await analyzeReport({
      text: textInput.value.trim(),
      title: activeModule.value.label,
      report_type: activeModule.value.report_type,
    });
    ElMessage.success("报告已开始生成");
    router.push({ name: "reports-list" });
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "触发分析失败");
    throw e;
  }
}

onMounted(() => {
  switchModule("m1");
});
</script>

<template>
  <div class="new-report-page">
    <p class="page-desc">
      选择业务模块，上传文档或直接输入文本，生成专属分析报告；完成后可基于报告进行智能问答。
    </p>

    <div class="card-panel modules-grid">
      <div
        v-for="m in MODULES"
        :key="m.key"
        class="module-card"
        :class="{ active: m.key === activeKey }"
        @click="switchModule(m.key)"
      >
        <div class="module-label">{{ m.label }}</div>
        <div class="module-desc">{{ m.desc }}</div>
      </div>
    </div>

    <div class="card-panel form-panel">
      <h3 class="form-title">{{ activeModule.label }}</h3>
      <p class="form-desc">{{ activeModule.desc }}</p>

      <template v-if="activeModule.mode === 'doc'">
        <div class="form-section">
          <label class="form-label">从已上传文档选择（可多选）：</label>
          <el-select
            v-model="selectedDocIds"
            placeholder="选择一个或多个文档"
            clearable
            filterable
            multiple
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="3"
            :loading="loadingDocs"
            style="width: 100%"
            no-data-text="暂无可用文档"
          >
            <el-option
              v-for="d in documents"
              :key="d.id"
              :label="docOptionLabel(d)"
              :value="d.id"
            />
          </el-select>
          <p v-if="!loadingDocs && !documents.length" class="doc-empty-hint">
            请先在
            <router-link to="/documents">我的文档</router-link>
            上传文件，并等待状态变为「完成」后再选择。也可直接在下方输入文本。
          </p>
        </div>
        <div class="form-section">
          <label class="form-label">或直接输入文本：</label>
          <el-input
            v-model="textInput"
            type="textarea"
            :rows="6"
            :placeholder="activeModule.text_placeholder"
          />
        </div>
      </template>

      <template v-else>
        <div class="form-section">
          <label class="form-label">输入内容：</label>
          <el-input
            v-model="textInput"
            type="textarea"
            :rows="10"
            :placeholder="activeModule.text_placeholder"
          />
        </div>
      </template>

      <div class="form-actions">
        <el-button
          type="primary"
          size="large"
          :loading="submitting || store.generating"
          @click="submit"
        >
          生成报告
        </el-button>
        <span class="hint">报告生成约 30-60 秒，可稍后在「报告」列表查看</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.new-report-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.module-card {
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.15s;
}

.module-card:hover {
  border-color: #93c5fd;
  background: #f8fafc;
}

.module-card.active {
  border-color: #f97316;
  background: #fff7ed;
}

.module-label {
  font-weight: 600;
  font-size: 14px;
  color: #9a3412;
  margin-bottom: 6px;
}

.module-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}

.form-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-title {
  margin: 0;
  font-size: 18px;
}

.form-desc {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
}

.hint {
  color: #94a3b8;
  font-size: 12px;
}

.doc-empty-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.doc-empty-hint a {
  color: #ea580c;
  font-weight: 600;
  text-decoration: none;
}

.doc-empty-hint a:hover {
  text-decoration: underline;
}
</style>
