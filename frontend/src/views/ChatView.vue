<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { globalAnswer } from '@/api/graph'
import { answer } from '@/api/search'
import type { AnswerResult, GlobalAnswerResult } from '@/types'

type Mode = 'local' | 'global'

const query = ref('')
const useGraph = ref(true)
const docType = ref('law')
const loading = ref(false)
const mode = ref<Mode>('local')
const localResult = ref<AnswerResult | null>(null)
const globalResult = ref<GlobalAnswerResult | null>(null)

async function askLocal() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  mode.value = 'local'
  loading.value = true
  localResult.value = null
  try {
    localResult.value = await answer({
      query: query.value.trim(),
      use_graph: useGraph.value,
      ...(docType.value ? { doc_type: docType.value } : {}),
    })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '问答失败')
  } finally {
    loading.value = false
  }
}

async function askGlobal() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  mode.value = 'global'
  loading.value = true
  globalResult.value = null
  try {
    globalResult.value = await globalAnswer({ query: query.value.trim(), depth: 2 })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '全局问答失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <p class="page-desc">
      局部问答基于 Hybrid RAG + 图谱上下文；全局问答走 GraphRAG 社区 map-reduce，适合跨文档宏观问题
    </p>

    <div class="card-panel input-panel">
      <el-input
        v-model="query"
        type="textarea"
        :rows="3"
        placeholder="例如：试用期最长多久？物业纠纷需要哪些证据？"
        @keyup.ctrl.enter="askLocal"
      />
      <div class="actions">
        <el-checkbox v-model="useGraph">启用图谱上下文</el-checkbox>
        <el-select v-model="docType" placeholder="检索范围" style="width:140px">
          <el-option label="法规" value="law" />
          <el-option label="类案" value="case" />
          <el-option label="全部" value="" />
        </el-select>
        <el-button type="primary" :loading="loading && mode === 'local'" @click="askLocal">
          局部问答
        </el-button>
        <el-button type="warning" :loading="loading && mode === 'global'" @click="askGlobal">
          全局 GraphRAG
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="results">
      <div v-if="mode === 'local' && localResult" class="card-panel answer-box">
        <div class="answer-meta">
          {{ localResult.sources.length }} 个来源 · {{ localResult.graph_entities.length }} 个图谱实体
        </div>
        <pre class="text-pre answer">{{ localResult.answer }}</pre>

        <el-collapse v-if="localResult.sources.length">
          <el-collapse-item title="引用来源" :name="1">
            <div v-for="(s, i) in localResult.sources" :key="s.chunk_id" class="source-item">
              <div class="source-title">
                #{{ i + 1 }} {{ s.source }} (score {{ s.score.toFixed(3) }})
              </div>
              <pre class="text-pre excerpt">{{ s.text.slice(0, 300) }}...</pre>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div v-if="mode === 'global' && globalResult" class="card-panel answer-box global">
        <div class="answer-meta">
          基于 {{ globalResult.communities_used ?? 0 }} 个社区的 GraphRAG 答案
        </div>
        <pre class="text-pre answer">{{ globalResult.answer }}</pre>

        <el-collapse v-if="globalResult.community_refs?.length">
          <el-collapse-item title="引用社区" :name="1">
            <div v-for="(c, i) in globalResult.community_refs" :key="i" class="source-item">
              <div class="source-title">{{ c.title }}</div>
              <pre class="text-pre excerpt">{{ c.partial_excerpt }}</pre>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input-panel {
  margin-bottom: 20px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.answer-meta {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

.answer {
  font-size: 15px;
  margin: 0 0 16px;
}

.global {
  border-left: 4px solid #7c3aed;
}

.source-item {
  margin-bottom: 12px;
  border-left: 2px solid #e2e8f0;
  padding-left: 10px;
}

.source-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}

.excerpt {
  font-size: 12px;
  color: #475569;
  margin: 0;
}
</style>
