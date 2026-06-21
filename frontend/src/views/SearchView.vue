<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { search } from '@/api/search'
import type { SearchResult } from '@/types'

const query = ref('')
const topK = ref(10)
const loading = ref(false)
const result = ref<SearchResult | null>(null)

async function runSearch() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入查询')
    return
  }
  loading.value = true
  try {
    result.value = await search({ query: query.value.trim(), top_k: topK.value, use_graph: true })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '检索失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <p class="page-desc">Hybrid 检索：Dense 向量 + BM25 + RRF 融合，可选图谱实体上下文</p>

    <div class="search-bar card-panel">
      <el-input
        v-model="query"
        placeholder="输入查询，如：劳动合同法第39条、物业纠纷类案..."
        clearable
        @keyup.enter="runSearch"
      />
      <el-input-number v-model="topK" :min="1" :max="50" />
      <el-button type="primary" :loading="loading" @click="runSearch">搜索</el-button>
    </div>

    <div v-loading="loading">
      <el-empty v-if="result && !result.hits.length" description="无匹配结果" />

      <div v-if="result?.hits.length" class="hits">
        <div v-for="(hit, i) in result.hits" :key="hit.chunk_id" class="card-panel hit-card">
          <div class="hit-meta">
            #{{ i + 1 }} · {{ hit.source || '未知来源' }} · score {{ hit.score.toFixed(4) }}
          </div>
          <pre class="text-pre">{{ hit.text }}</pre>
        </div>
      </div>

      <div v-if="result?.graph_context?.length" class="card-panel graph-ctx">
        <h4>图谱关联实体（{{ result.graph_context.length }}）</h4>
        <div class="tags">
          <el-tag v-for="(g, i) in result.graph_context.slice(0, 16)" :key="i" class="tag">
            {{ g.name }} <span class="type">({{ g.type }})</span>
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.hits {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hit-meta {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.graph-ctx {
  margin-top: 16px;
}

.graph-ctx h4 {
  margin: 0 0 12px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.type {
  color: #94a3b8;
}
</style>
