<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createConversation } from '@/api/conversations'
import { useReportsStore } from '@/stores/reports'
import type { RiskItem, SourceType } from '@/types'

const route = useRoute()
const router = useRouter()
const store = useReportsStore()

const polling = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const levelTagType: Record<RiskItem['level'], 'danger' | 'warning' | 'info'> = {
  高: 'danger',
  中: 'warning',
  低: 'info',
}

const sourceTagType: Record<SourceType, 'success' | 'warning' | 'info' | 'primary' | 'danger'> = {
  law: 'primary',
  case: 'success',
  report: 'warning',
  user_doc: 'info',
  compliance: 'primary',
  graph: 'danger',
}

const sourceTagText: Record<SourceType, string> = {
  law: '法规',
  case: '类案',
  report: '报告',
  user_doc: '材料',
  compliance: '合规',
  graph: '图谱',
}

const reportTypeLabel: Record<string, string> = {
  contract_review: '合同审查',
  dispute_analysis: '纠纷研判',
  labor_risk: '用工风险',
  litigation_draft: '诉讼文书',
  evidence_checklist: '证据指引',
}

async function load() {
  const id = route.params.id as string
  await store.loadOne(id)
  if (store.currentReport && (store.currentReport.status === 'pending' || store.currentReport.status === 'generating')) {
    startPolling(id)
  }
}

function startPolling(id: string) {
  polling.value = true
  pollTimer = setInterval(async () => {
    try {
      const r = await store.pollUntilDone(id, 1_000)
      if (r.status === 'done' || r.status === 'failed') {
        stopPolling()
      }
    } catch (e) {
      stopPolling()
      ElMessage.error(e instanceof Error ? e.message : '生成失败')
    }
  }, 2000)
}

function stopPolling() {
  polling.value = false
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function startReportChat() {
  if (!store.currentReport) return
  try {
    const conv = await createConversation({
      title: `${reportTypeLabel[store.currentReport.type] || '报告'}问答`,
      report_ids: [store.currentReport.id],
    })
    router.push({ name: 'chat-with-conversation', params: { conversationId: conv.id } })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建会话失败')
  }
}

onMounted(load)
onUnmounted(stopPolling)
</script>

<template>
  <div v-loading="store.loading || polling">
    <div v-if="store.currentReport" class="report-page">
      <div class="card-panel header-card">
        <div class="header-row">
          <div>
            <h2 class="title">
              {{ reportTypeLabel[store.currentReport.type] || store.currentReport.type }}
            </h2>
            <p v-if="store.currentReport.summary" class="summary">{{ store.currentReport.summary }}</p>
          </div>
          <div class="meta">
            <el-tag v-if="store.currentReport.status === 'done'" type="success">完成</el-tag>
            <el-tag v-else-if="store.currentReport.status === 'failed'" type="danger">失败</el-tag>
            <el-tag v-else type="warning">{{ store.currentReport.status === 'pending' ? '排队中' : '生成中' }}</el-tag>
            <el-progress
              v-if="store.currentReport.status !== 'done' && store.currentReport.status !== 'failed'"
              :percentage="store.currentReport.status === 'generating' ? 60 : 20"
              :indeterminate="true"
              style="width: 140px"
            />
            <div v-if="store.currentReport.confidence" class="confidence">
              置信度 {{ store.currentReport.confidence }} / 100
            </div>
          </div>
        </div>
        <el-button
          v-if="store.currentReport.status === 'done'"
          type="primary"
          @click="startReportChat"
        >
          基于此报告问答
        </el-button>
      </div>

      <el-alert
        v-if="store.currentReport.error"
        type="error"
        :title="store.currentReport.error"
        :closable="false"
        style="margin-bottom: 16px"
      />

      <div v-if="store.currentReport.risk_items.length" class="card-panel">
        <h3 class="section-title">风险项 ({{ store.currentReport.risk_items.length }})</h3>
        <el-table :data="store.currentReport.risk_items" stripe>
          <el-table-column label="级别" width="80">
            <template #default="{ row }">
              <el-tag :type="levelTagType[row.level as RiskItem['level']]" size="small">
                {{ row.level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="desc" label="描述" min-width="280" />
          <el-table-column prop="law_ref" label="法条" width="200" />
          <el-table-column prop="suggestion" label="修改建议" min-width="280" />
        </el-table>
      </div>

      <template v-if="store.currentReport.type === 'litigation_draft'">
        <div v-if="store.currentReport.parties" class="card-panel">
          <h3 class="section-title">当事人</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="原告">
              {{ store.currentReport.parties.plaintiff || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="被告">
              {{ store.currentReport.parties.defendant || '—' }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div v-if="store.currentReport.claims?.length" class="card-panel">
          <h3 class="section-title">诉讼请求</h3>
          <ol class="point-list">
            <li v-for="(c, i) in store.currentReport.claims" :key="i">{{ c }}</li>
          </ol>
        </div>

        <div v-if="store.currentReport.facts?.length" class="card-panel">
          <h3 class="section-title">事实与理由</h3>
          <pre v-for="(f, i) in store.currentReport.facts" :key="i" class="text-pre fact-text">{{ f }}</pre>
        </div>

        <div v-if="store.currentReport.evidence_list?.length" class="card-panel">
          <h3 class="section-title">证据清单</h3>
          <el-table :data="store.currentReport.evidence_list" stripe>
            <el-table-column label="序号" width="70" type="index" />
            <el-table-column prop="name" label="证据名称" min-width="200" />
            <el-table-column prop="purpose" label="证明目的" min-width="240" />
          </el-table>
        </div>
      </template>

      <template v-if="store.currentReport.type === 'evidence_checklist'">
        <div v-if="store.currentReport.evidence_items?.length" class="card-panel">
          <h3 class="section-title">证据清单 ({{ store.currentReport.evidence_items.length }})</h3>
          <el-table :data="store.currentReport.evidence_items" stripe>
            <el-table-column label="关键程度" width="100">
              <template #default="{ row }">
                <el-tag :type="levelTagType[row.level as RiskItem['level']]" size="small">
                  {{ row.level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="证据名称" min-width="180" />
            <el-table-column prop="purpose" label="证明目的" min-width="200" />
            <el-table-column prop="collect_tip" label="取证要点" min-width="240" />
          </el-table>
        </div>

        <div v-if="store.currentReport.procedure_steps?.length" class="card-panel">
          <h3 class="section-title">举证流程</h3>
          <el-steps direction="vertical">
            <el-step
              v-for="(step, i) in store.currentReport.procedure_steps"
              :key="i"
              :title="`步骤 ${i + 1}`"
              :description="step"
            />
          </el-steps>
        </div>
      </template>

      <div v-if="store.currentReport.citations.length" class="card-panel">
        <h3 class="section-title">引用来源 ({{ store.currentReport.citations.length }})</h3>
        <el-collapse>
          <el-collapse-item
            v-for="(c, i) in store.currentReport.citations"
            :key="i"
            :name="i"
          >
            <template #title>
              <el-tag :type="sourceTagType[c.source_type]" size="small">
                {{ sourceTagText[c.source_type] }}
              </el-tag>
              <span class="citation-title">{{ c.source_title }}</span>
            </template>
            <pre v-if="c.excerpt" class="text-pre excerpt">{{ c.excerpt }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div v-if="store.currentReport.suggested_questions.length" class="card-panel">
        <h3 class="section-title">建议追问</h3>
        <div class="suggested-list">
          <el-button
            v-for="(q, i) in store.currentReport.suggested_questions"
            :key="i"
            round
            @click="startReportChat"
          >
            {{ q }}
          </el-button>
        </div>
      </div>

      <div v-if="store.currentReport.graph_path.length" class="card-panel">
        <h3 class="section-title">图谱路径</h3>
        <el-tag v-for="(p, i) in store.currentReport.graph_path" :key="i" class="graph-tag">
          {{ p }}
        </el-tag>
      </div>
    </div>

    <el-empty v-else-if="!store.loading" description="未找到报告" />
  </div>
</template>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.title {
  margin: 0 0 6px;
  font-size: 18px;
}

.summary {
  margin: 0;
  color: #475569;
  font-size: 14px;
}

.meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.confidence {
  font-size: 12px;
  color: #64748b;
}

.section-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}

.point-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.8;
  color: #1e293b;
}

.point-list li {
  margin-bottom: 4px;
}

.fact-text {
  font-size: 14px;
  color: #334155;
  margin: 0 0 8px;
  white-space: pre-wrap;
}

.citation-title {
  margin-left: 8px;
  font-weight: 600;
}

.excerpt {
  font-size: 13px;
  color: #475569;
  margin: 0;
  white-space: pre-wrap;
}

.suggested-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.graph-tag {
  margin-right: 6px;
  margin-bottom: 6px;
}
</style>
