<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import GraphCanvas from '@/components/GraphCanvas.vue'
import { listCommunities, localGraph, rebuildCommunities } from '@/api/graph'
import type { Community, GraphNode } from '@/types'

const query = ref('智芯科技 NeuroScale 阿里云')
const depth = ref(2)
const loading = ref(false)
const rebuilding = ref(false)
const entities = ref<GraphNode[]>([])
const relations = ref<Array<{ source: string; target: string }>>([])
const communities = ref<Community[]>([])
const showCommunities = ref(false)

async function loadLocal() {
  if (!query.value.trim()) return
  loading.value = true
  try {
    const r = await localGraph({ query: query.value.trim(), depth: depth.value })
    entities.value = r.entities
    relations.value = r.relations
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '查询失败')
  } finally {
    loading.value = false
  }
}

async function loadCommunities() {
  loading.value = true
  try {
    communities.value = await listCommunities()
    showCommunities.value = true
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载社区失败')
  } finally {
    loading.value = false
  }
}

async function rebuild() {
  rebuilding.value = true
  try {
    const r = await rebuildCommunities()
    ElMessage.success(`重建完成：${r.communities ?? 0} 个社区，覆盖 ${r.entities_covered ?? 0} 个实体`)
    await loadCommunities()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '重建失败')
  } finally {
    rebuilding.value = false
  }
}
</script>

<template>
  <div>
    <p class="page-desc">Neo4j 实体关系可视化，支持局部遍历与 GraphRAG 社区检测</p>

    <div class="toolbar card-panel">
      <el-input v-model="query" placeholder="实体名 / 查询文本" class="flex-1" />
      <el-input-number v-model="depth" :min="1" :max="3" />
      <el-button type="primary" :loading="loading" @click="loadLocal">局部遍历</el-button>
      <el-button @click="loadCommunities">查看社区</el-button>
      <el-button type="warning" :loading="rebuilding" @click="rebuild">重建社区</el-button>
    </div>

    <div class="graph-layout">
      <div v-loading="loading" class="card-panel graph-main">
        <GraphCanvas :entities="entities" :relations="relations" />
      </div>
      <div class="card-panel graph-side">
        <h4>实体列表（{{ entities.length }}）</h4>
        <el-empty v-if="!entities.length" description="执行局部遍历后显示" />
        <div v-else class="entity-list">
          <div v-for="e in entities" :key="e.id" class="entity-item">
            <div class="name">{{ e.name }}</div>
            <div class="type">{{ e.type }}</div>
            <div v-if="e.description" class="desc">{{ e.description.slice(0, 80) }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showCommunities" class="card-panel mt">
      <h4>社区列表</h4>
      <el-empty v-if="!communities.length" description="暂无社区，请先重建" />
      <div v-else class="community-grid">
        <div v-for="c in communities" :key="c.id" class="community-card">
          <div class="title">{{ c.title || '(无标题)' }}</div>
          <div class="meta">level {{ c.level }} · {{ c.id.slice(0, 8) }}</div>
          <p>{{ c.summary }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.flex-1 {
  flex: 1;
  min-width: 200px;
}

.graph-layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

.graph-side {
  max-height: 540px;
  overflow-y: auto;
}

.graph-side h4 {
  margin: 0 0 12px;
}

.entity-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.entity-item {
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 8px;
}

.name {
  font-weight: 600;
}

.type,
.desc {
  font-size: 12px;
  color: #64748b;
}

.mt {
  margin-top: 16px;
}

.community-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.community-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
}

.community-card .title {
  font-weight: 600;
}

.community-card .meta {
  font-size: 12px;
  color: #94a3b8;
  margin: 4px 0 8px;
}

.community-card p {
  margin: 0;
  font-size: 13px;
  color: #475569;
}

@media (max-width: 960px) {
  .graph-layout {
    grid-template-columns: 1fr;
  }
}
</style>
