<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listDocuments } from '@/api/documents'
import { useReportsStore } from '@/stores/reports'
import type { DocumentItem, ReportType } from '@/types'

type ModuleKey = 'm1' | 'm2' | 'm3' | 'm4' | 'm5'

interface ModuleSpec {
  key: ModuleKey
  label: string
  desc: string
  report_type: ReportType
  mode: 'doc' | 'text'
  doc_type?: string
  text_placeholder: string
  text_default?: string
}

const MODULES: ModuleSpec[] = [
  {
    key: 'm1',
    label: 'M1 纠纷研判',
    desc: '上传纠纷材料（事实、证据），生成纠纷研判报告：案由、证据清单、调解建议',
    report_type: 'dispute_analysis',
    mode: 'doc',
    doc_type: 'dispute',
    text_placeholder: '或直接粘贴纠纷描述（无需上传文件）',
  },
  {
    key: 'm2',
    label: 'M2 合同审查',
    desc: '上传合同 PDF，自动识别风险条款（试用期/违约金/管辖等），生成审查报告',
    report_type: 'contract_review',
    mode: 'doc',
    doc_type: 'contract',
    text_placeholder: '或直接粘贴合同条款文本',
  },
  {
    key: 'm3',
    label: 'M3 用工风险排查',
    desc: '粘贴用工合同或描述用工情形，规则引擎 + 法规库生成劳动用工风险报告',
    report_type: 'labor_risk',
    mode: 'text',
    text_placeholder: '粘贴劳动合同条款或用工情形描述。例如：约定试用期一年，加班无加班费，未缴纳社保...',
  },
  {
    key: 'm4',
    label: 'M4 诉讼文书生成',
    desc: '输入案由与事实，生成起诉状 / 答辩状草稿',
    report_type: 'litigation_draft',
    mode: 'text',
    text_placeholder: '描述案由与事实。例如：案由：物业服务合同纠纷。事实：原告入住后物业不履行维修义务...',
  },
  {
    key: 'm5',
    label: 'M5 证据清单指引',
    desc: '选择案由，输出该类纠纷需要的证据清单 + 举证流程',
    report_type: 'evidence_checklist',
    mode: 'text',
    text_placeholder: '输入案由（如：物业纠纷、借贷纠纷、劳动争议），生成证据清单',
  },
]

const router = useRouter()
const store = useReportsStore()

const activeKey = ref<ModuleKey>('m2')
const documents = ref<DocumentItem[]>([])
const selectedDocId = ref<string>('')
const textInput = ref<string>('')
const submitting = ref(false)

const activeModule = computed(() => MODULES.find((m) => m.key === activeKey.value) as ModuleSpec)

async function loadDocuments() {
  try {
    const all = await listDocuments({})
    documents.value = all.filter(
      (d) => d.status === 'done' && d.metadata?.doc_type === activeModule.value.doc_type,
    )
  } catch {
    documents.value = []
  }
}

function switchModule(key: ModuleKey) {
  activeKey.value = key
  selectedDocId.value = ''
  textInput.value = activeModule.value.text_default || ''
  if (activeModule.value.mode === 'doc') {
    loadDocuments()
  }
}

async function submit() {
  if (activeModule.value.mode === 'doc' && !selectedDocId.value && !textInput.value.trim()) {
    ElMessage.warning('请选择已上传文档，或直接输入文本')
    return
  }
  if (activeModule.value.mode === 'text' && !textInput.value.trim()) {
    ElMessage.warning('请输入文本内容')
    return
  }

  submitting.value = true
  try {
    const r = await store.triggerAnalyze(
      selectedDocId.value,
      activeModule.value.report_type,
    )
    if (!selectedDocId.value && textInput.value.trim()) {
      await triggerViaText()
      return
    }
    ElMessage.success('已触发报告生成')
    router.push({ name: 'report-view', params: { id: r.id } })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '触发分析失败')
  } finally {
    submitting.value = false
  }
}

async function triggerViaText() {
  const { analyzeReport } = await import('@/api/reports')
  try {
    const r = await analyzeReport({
      text: textInput.value.trim(),
      title: activeModule.value.label,
      report_type: activeModule.value.report_type,
    })
    ElMessage.success('已触发报告生成')
    router.push({ name: 'report-view', params: { id: r.id } })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '触发分析失败')
    throw e
  }
}

onMounted(() => {
  switchModule('m2')
})
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
          <label class="form-label">从已上传文档选择（推荐）：</label>
          <el-select
            v-model="selectedDocId"
            placeholder="选择文档"
            clearable
            filterable
            style="width: 100%"
            no-data-text="暂无符合条件的文档，可上传后重试或直接输入文本"
          >
            <el-option
              v-for="d in documents"
              :key="d.id"
              :label="d.title"
              :value="d.id"
            />
          </el-select>
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
  background: #f8FAFC;
}

.module-card.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.module-label {
  font-weight: 600;
  font-size: 14px;
  color: #1e3a8a;
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
</style>
