<script setup lang="ts">
import { ref } from 'vue'
import { search } from '@/api/search'
import { notifyError, notifyInfo, notifyWarning } from '@/utils/notify'
import DatasetScopeSelect from '@/components/DatasetScopeSelect.vue'
import { useKnowledgeContextStore } from '@/stores/knowledgeContext'
import type { SearchResult } from '@/types'

const kb = useKnowledgeContextStore()

const query = ref('')
const topK = ref(10)
const docType = ref('')
const loading = ref(false)
const result = ref<SearchResult | null>(null)

async function runSearch() {
  if (!kb.selectedDatasetId) {
    notifyWarning('请先选择知识库')
    return
  }
  if (!query.value.trim()) {
    notifyWarning('请输入查询', '例如：试用期最长多久、违法解除劳动合同')
    return
  }
  loading.value = true
  try {
    result.value = await search({
      query: query.value.trim(),
      top_k: topK.value,
      use_graph: true,
      dataset_id: kb.selectedDatasetId,
      ...(docType.value ? { doc_type: docType.value } : {}),
    })
    if (result.value && !result.value.hits.length) {
      notifyInfo('无匹配结果', '可换关键词、取消文档类型过滤，或确认该知识库文档已入库完成')
    }
  } catch (e) {
    notifyError('检索失败', e instanceof Error ? e.message : undefined)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <p class="page-desc">
      在选定知识库内进行 Hybrid 检索：Dense 向量 + BM25 + RRF 融合，可选图谱实体上下文
    </p>

    <div class="search-bar card-panel">
      <DatasetScopeSelect width="220px" />
      <el-input
        v-model="query"
        placeholder="输入查询，如：劳动合同法第39条、物业纠纷类案..."
        clearable
        class="grow"
        @keyup.enter="runSearch"
      />
      <el-select v-model="docType" placeholder="文档类型" clearable style="width:140px">
        <el-option label="法规 law" value="law" />
        <el-option label="类案 case" value="case" />
        <el-option label="合规 compliance" value="compliance" />
        <el-option label="默认库 default" value="default" />
        <el-option label="合同 contract" value="contract" />
        <el-option label="纠纷 dispute" value="dispute" />
        <el-option label="通用 general" value="general" />
      </el-select>
      <el-input-number v-model="topK" :min="1" :max="50" />
      <el-button type="primary" :loading="loading" @click="runSearch">搜索</el-button>
    </div>

    <p v-if="kb.selectedDataset" class="scope-hint">
      当前范围：<strong>{{ kb.selectedDataset.name }}</strong>
    </p>

    <div v-loading="loading">
      <el-empty v-if="result && !result.hits.length" description="无匹配结果" />

      <div v-if="result?.hits.length" class="hits">
        <div v-for="(hit, i) in result.hits" :key="hit.chunk_id" class="card-panel hit-card">
          <div class="hit-meta">
            #{{ i + 1 }} · {{ hit.source || '未知来源' }}
            <span v-if="hit.article_no"> · {{ hit.law_name }} {{ hit.article_no }}</span>
            · score {{ hit.score.toFixed(4) }}
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
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
  align-items: center;
}

.grow {
  flex: 1;
  min-width: 200px;
}

.scope-hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--text-muted);
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
