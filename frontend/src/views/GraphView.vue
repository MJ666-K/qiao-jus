<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import GraphCanvas from '@/components/GraphCanvas.vue'
import {
  createGraphRelation,
  deleteGraphRelation,
  listCommunities,
  localGraph,
  rebuildCommunities,
} from '@/api/graph'
import { useAuthStore } from '@/stores/auth'
import { notifyError, notifyInfo, notifySuccess, notifyWarning } from '@/utils/notify'
import type { Community, GraphEdge, GraphNode } from '@/types'

const auth = useAuthStore()
const router = useRouter()
const canvasRef = ref<InstanceType<typeof GraphCanvas>>()
const loggedIn = computed(() => !!auth.user?.id)

const query = ref('')
const depth = ref(2)
const loading = ref(false)
const rebuilding = ref(false)
const linkMode = ref(false)
const entities = ref<GraphNode[]>([])
const relations = ref<GraphEdge[]>([])
const graphKey = ref(0)
const communities = ref<Community[]>([])
const showCommunities = ref(false)
const lastEmpty = ref(false)

const drawerOpen = ref(false)
const drawerMode = ref<'entity' | 'relation'>('entity')
const selectedEntityId = ref<string | null>(null)
const selectedRelation = ref<GraphEdge | null>(null)

const examples = ['违法解除劳动合同', '物业服务合同', '试用期', '加班费', '违约金']

const entityById = computed(() => new Map(entities.value.map((e) => [e.id, e])))

const selectedEntity = computed(() =>
  selectedEntityId.value ? entityById.value.get(selectedEntityId.value) ?? null : null,
)

const selectedRelationKey = computed(() => {
  const r = selectedRelation.value
  return r ? `${r.source}->${r.target}:${r.type ?? 'RELATED'}` : null
})

const entityRelations = computed(() => {
  if (!selectedEntityId.value) return { out: [] as GraphEdge[], in: [] as GraphEdge[] }
  const id = selectedEntityId.value
  return {
    out: relations.value.filter((r) => r.source === id),
    in: relations.value.filter((r) => r.target === id),
  }
})

function relName(id: string) {
  return entityById.value.get(id)?.name ?? id.split(':').pop() ?? id
}

function relationKey(r: GraphEdge) {
  return `${r.source}->${r.target}:${r.type ?? 'RELATED'}`
}

function openEntity(id: string) {
  selectedEntityId.value = id
  selectedRelation.value = null
  drawerMode.value = 'entity'
  drawerOpen.value = true
}

function openRelation(r: GraphEdge) {
  selectedRelation.value = r
  selectedEntityId.value = null
  drawerMode.value = 'relation'
  drawerOpen.value = true
}

onMounted(async () => {
  await auth.ensureUser()
})

async function loadLocal() {
  if (!loggedIn.value) {
    notifyWarning('请先登录', '演示账号 seed@demo.com / seed12345')
    router.push({ path: '/login', query: { redirect: '/graph' } })
    return
  }
  if (!query.value.trim()) {
    notifyWarning('请输入查询内容')
    return
  }
  loading.value = true
  lastEmpty.value = false
  linkMode.value = false
  drawerOpen.value = false
  try {
    const r = await localGraph({ query: query.value.trim(), depth: depth.value })
    entities.value = [...r.entities]
    relations.value = [...r.relations]
    graphKey.value += 1
    lastEmpty.value = entities.value.length === 0
    if (lastEmpty.value) {
      notifyInfo('未找到关联实体', '可换关键词重试')
    } else {
      notifySuccess('查询完成', `${entities.value.length} 个实体 · ${relations.value.length} 条关系`)
    }
  } catch (e) {
    notifyError('图谱查询失败', e instanceof Error ? e.message : undefined)
  } finally {
    loading.value = false
  }
}

function useExample(text: string) {
  query.value = text
  loadLocal()
}

async function onCreateRelation(payload: { source: string; target: string }) {
  try {
    const edge = await createGraphRelation(payload)
    if (!relations.value.some((r) => relationKey(r) === relationKey(edge))) {
      relations.value = [...relations.value, edge]
    }
    openRelation(edge)
    notifySuccess('已建立关系')
  } catch (e) {
    notifyError('建立关系失败', e instanceof Error ? e.message : undefined)
  }
}

async function deleteSelectedRelation() {
  const r = selectedRelation.value
  if (!r) return
  try {
    await ElMessageBox.confirm(
      `删除 ${relName(r.source)} → ${relName(r.target)} ？`,
      '删除关系',
      { type: 'warning' },
    )
    await deleteGraphRelation(r.source, r.target)
    relations.value = relations.value.filter((x) => relationKey(x) !== relationKey(r))
    drawerOpen.value = false
    selectedRelation.value = null
    notifySuccess('已删除')
  } catch (e) {
    if (e === 'cancel' || (e instanceof Error && e.message === 'cancel')) return
    notifyError('删除失败', e instanceof Error ? e.message : undefined)
  }
}

async function loadCommunities() {
  if (!loggedIn.value) return notifyWarning('请先登录')
  loading.value = true
  try {
    communities.value = await listCommunities()
    showCommunities.value = true
  } catch (e) {
    notifyError('加载失败', e instanceof Error ? e.message : undefined)
  } finally {
    loading.value = false
  }
}

async function rebuild() {
  if (!loggedIn.value) return notifyWarning('请先登录')
  rebuilding.value = true
  try {
    const r = await rebuildCommunities()
    notifySuccess('重建完成', `${r.communities ?? 0} 个社区`)
    await loadCommunities()
  } catch (e) {
    notifyError('重建失败', e instanceof Error ? e.message : undefined)
  } finally {
    rebuilding.value = false
  }
}
</script>

<template>
  <div>
    <el-alert
      v-if="!loggedIn"
      type="warning"
      show-icon
      :closable="false"
      title="请先登录"
      class="mb"
    />

    <div class="toolbar card-panel">
      <el-input
        v-model="query"
        placeholder="输入问题或实体名"
        class="flex-1"
        clearable
        @keyup.enter="loadLocal"
      />
      <el-input-number v-model="depth" :min="1" :max="3" />
      <el-button type="primary" :loading="loading" @click="loadLocal">局部遍历</el-button>
      <el-button @click="loadCommunities">查看社区</el-button>
      <el-button type="warning" :loading="rebuilding" @click="rebuild">重建社区</el-button>
    </div>

    <div class="examples">
      <el-tag v-for="ex in examples" :key="ex" class="ex-tag" effect="plain" @click="useExample(ex)">
        {{ ex }}
      </el-tag>
    </div>

    <div class="graph-layout">
      <div class="card-panel graph-main">
        <div class="canvas-toolbar">
          <el-button size="small" @click="canvasRef?.zoomIn()">放大</el-button>
          <el-button size="small" @click="canvasRef?.zoomOut()">缩小</el-button>
          <el-button size="small" @click="canvasRef?.resetZoom()">重置</el-button>
          <el-button size="small" :type="linkMode ? 'warning' : 'default'" @click="linkMode = !linkMode">
            {{ linkMode ? '退出连线' : '建立关系' }}
          </el-button>
        </div>
        <div v-if="loading" class="graph-loading">
          <el-icon class="spin"><Loading /></el-icon>
        </div>
        <GraphCanvas
          :key="graphKey"
          ref="canvasRef"
          :graph-entities="entities"
          :graph-relations="relations"
          :link-mode="linkMode"
          :selected-entity-id="selectedEntityId"
          :selected-relation-key="selectedRelationKey"
          @create-relation="onCreateRelation"
          @select-entity="openEntity"
          @select-relation="openRelation"
        />
      </div>

      <div class="graph-side-wrap">
        <div class="card-panel graph-side">
          <h4>实体</h4>
          <el-empty v-if="!entities.length" description="暂无" />
          <div v-else class="name-list">
            <div
              v-for="e in entities"
              :key="e.id"
              class="name-item"
              :class="{ active: selectedEntityId === e.id }"
              @click="openEntity(e.id)"
            >
              {{ e.name }}
            </div>
          </div>
        </div>

        <div class="card-panel graph-side">
          <h4>关系</h4>
          <el-empty v-if="!relations.length" description="暂无" />
          <div v-else class="name-list">
            <div
              v-for="r in relations"
              :key="relationKey(r)"
              class="name-item"
              :class="{ active: selectedRelationKey === relationKey(r) }"
              @click="openRelation(r)"
            >
              {{ relName(r.source) }} → {{ relName(r.target) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-drawer
      v-model="drawerOpen"
      :title="drawerMode === 'entity' ? selectedEntity?.name ?? '实体' : '关系详情'"
      direction="rtl"
      size="360px"
    >
      <template v-if="drawerMode === 'entity' && selectedEntity">
        <dl class="detail-dl">
          <dt>名称</dt>
          <dd>{{ selectedEntity.name }}</dd>
          <dt>类型</dt>
          <dd>{{ selectedEntity.type || '—' }}</dd>
          <dt>描述</dt>
          <dd>{{ selectedEntity.description?.trim() || '—' }}</dd>
          <dt>标识</dt>
          <dd class="mono">{{ selectedEntity.id }}</dd>
        </dl>

        <h5 class="detail-section">出边</h5>
        <el-empty v-if="!entityRelations.out.length" description="无" :image-size="48" />
        <ul v-else class="rel-mini">
          <li v-for="r in entityRelations.out" :key="'o' + relationKey(r)" @click="openRelation(r)">
            → {{ relName(r.target) }}
            <span class="rel-type">{{ r.type || '关联' }}</span>
          </li>
        </ul>

        <h5 class="detail-section">入边</h5>
        <el-empty v-if="!entityRelations.in.length" description="无" :image-size="48" />
        <ul v-else class="rel-mini">
          <li v-for="r in entityRelations.in" :key="'i' + relationKey(r)" @click="openRelation(r)">
            ← {{ relName(r.source) }}
            <span class="rel-type">{{ r.type || '关联' }}</span>
          </li>
        </ul>
      </template>

      <template v-else-if="drawerMode === 'relation' && selectedRelation">
        <dl class="detail-dl">
          <dt>起点</dt>
          <dd>
            <el-button link type="primary" @click="openEntity(selectedRelation.source)">
              {{ relName(selectedRelation.source) }}
            </el-button>
          </dd>
          <dt>终点</dt>
          <dd>
            <el-button link type="primary" @click="openEntity(selectedRelation.target)">
              {{ relName(selectedRelation.target) }}
            </el-button>
          </dd>
          <dt>关系类型</dt>
          <dd>{{ selectedRelation.type || 'RELATED' }}</dd>
          <dt>描述</dt>
          <dd>{{ selectedRelation.description?.trim() || '—' }}</dd>
          <dt v-if="selectedRelation.weight">权重</dt>
          <dd v-if="selectedRelation.weight">{{ selectedRelation.weight }}</dd>
        </dl>
        <el-button type="danger" plain class="full-btn" @click="deleteSelectedRelation">删除此关系</el-button>
      </template>
    </el-drawer>

    <div v-if="showCommunities" class="card-panel mt">
      <h4>社区</h4>
      <el-empty v-if="!communities.length" description="暂无" />
      <div v-else class="community-grid">
        <div v-for="c in communities" :key="c.id" class="community-card">
          <div class="title">{{ c.title || '未命名' }}</div>
          <p>{{ c.summary }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mb { margin-bottom: 12px; }
.examples { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.ex-tag { cursor: pointer; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.flex-1 { flex: 1; min-width: 200px; }
.graph-layout { display: grid; grid-template-columns: 1fr 220px; gap: 16px; }
.graph-main { position: relative; min-height: 520px; }
.canvas-toolbar {
  display: flex; gap: 8px; flex-wrap: wrap;
  margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #e2e8f0;
}
.graph-loading {
  position: absolute; inset: 48px 0 0; z-index: 2;
  display: grid; place-items: center; background: rgb(255 255 255 / 70%);
}
.graph-loading .spin { font-size: 28px; color: #2563eb; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.graph-side-wrap { display: flex; flex-direction: column; gap: 12px; }
.graph-side { max-height: 260px; overflow-y: auto; }
.graph-side h4 { margin: 0 0 10px; font-size: 15px; }
.name-list { display: flex; flex-direction: column; gap: 2px; }
.name-item {
  padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 13px;
  line-height: 1.4; word-break: break-all;
}
.name-item:hover { background: #f1f5f9; }
.name-item.active { background: #eff6ff; color: #1d4ed8; }
.detail-dl { margin: 0 0 16px; }
.detail-dl dt { font-size: 12px; color: #94a3b8; margin-top: 12px; }
.detail-dl dt:first-child { margin-top: 0; }
.detail-dl dd { margin: 4px 0 0; font-size: 14px; color: #1e293b; word-break: break-all; }
.detail-dl .mono { font-family: ui-monospace, monospace; font-size: 12px; color: #64748b; }
.detail-section { margin: 16px 0 8px; font-size: 14px; }
.rel-mini { list-style: none; margin: 0; padding: 0; }
.rel-mini li {
  padding: 8px 0; border-bottom: 1px solid #f1f5f9; cursor: pointer; font-size: 13px;
}
.rel-mini li:hover { color: #2563eb; }
.rel-type { margin-left: 8px; font-size: 12px; color: #94a3b8; }
.full-btn { width: 100%; margin-top: 16px; }
.mt { margin-top: 16px; }
.community-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.community-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
.community-card .title { font-weight: 600; margin-bottom: 8px; }
.community-card p { margin: 0; font-size: 13px; color: #475569; }
@media (max-width: 960px) { .graph-layout { grid-template-columns: 1fr; } }
</style>
