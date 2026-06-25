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

    <div class="toolbar-row card-panel">
      <el-input
        v-model="query"
        placeholder="输入问题或实体名"
        class="grow"
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

    </div>

    <el-drawer
      v-model="drawerOpen"
      :title="drawerMode === 'entity' ? selectedEntity?.name ?? '实体详情' : '关系详情'"
      direction="rtl"
      size="380px"
    >
      <div class="drawer-content">
        <template v-if="drawerMode === 'entity' && selectedEntity">
          <div class="info-card">
            <div class="info-label">名称</div>
            <div class="info-value">{{ selectedEntity.name }}</div>
          </div>

          <div class="info-item">
            <dl class="detail-dl" style="margin:0">
              <dt>类型</dt>
              <dd>{{ selectedEntity.type || '未知' }}</dd>
            </dl>
          </div>

          <div class="info-item" v-if="selectedEntity.description?.trim()">
            <dl class="detail-dl" style="margin:0">
              <dt>描述</dt>
              <dd>{{ selectedEntity.description?.trim() }}</dd>
            </dl>
          </div>

          <div class="info-item">
            <dl class="detail-dl" style="margin:0">
              <dt>标识</dt>
              <dd class="mono">{{ selectedEntity.id }}</dd>
            </dl>
          </div>

          <h5 class="detail-section">出边 ({{ entityRelations.out.length }})</h5>
          <el-empty v-if="!entityRelations.out.length" description="暂无出边" :image-size="48" />
          <ul v-else class="rel-mini">
            <li v-for="r in entityRelations.out" :key="'o' + relationKey(r)" @click="openRelation(r)">
              <span>→ {{ relName(r.target) }}</span>
              <span class="rel-type">{{ r.type || '关联' }}</span>
            </li>
          </ul>

          <h5 class="detail-section">入边 ({{ entityRelations.in.length }})</h5>
          <el-empty v-if="!entityRelations.in.length" description="暂无入边" :image-size="48" />
          <ul v-else class="rel-mini">
            <li v-for="r in entityRelations.in" :key="'i' + relationKey(r)" @click="openRelation(r)">
              <span>← {{ relName(r.source) }}</span>
              <span class="rel-type">{{ r.type || '关联' }}</span>
            </li>
          </ul>
        </template>

        <template v-else-if="drawerMode === 'relation' && selectedRelation">
          <div class="relation-flow">
            <div class="node">
              <div class="node-label">起点</div>
              <div class="node-name" @click="openEntity(selectedRelation.source)">
                {{ relName(selectedRelation.source) }}
              </div>
            </div>
            <div class="arrow">→</div>
            <div class="node">
              <div class="node-label">终点</div>
              <div class="node-name" @click="openEntity(selectedRelation.target)">
                {{ relName(selectedRelation.target) }}
              </div>
            </div>
          </div>

          <div class="rel-tags">
            <span class="rel-tag type">{{ selectedRelation.type || 'RELATED' }}</span>
            <span class="rel-tag desc" v-if="selectedRelation.description?.trim()">
              {{ selectedRelation.description?.trim() }}
            </span>
          </div>

          <div class="info-item" v-if="selectedRelation.weight">
            <dl class="detail-dl" style="margin:0">
              <dt>权重</dt>
              <dd>{{ selectedRelation.weight }}</dd>
            </dl>
          </div>

          <el-button type="danger" plain class="full-btn" @click="deleteSelectedRelation">
            删除此关系
          </el-button>
        </template>
      </div>
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
.graph-layout { display: grid; grid-template-columns: 1fr; gap: 16px; }
.graph-main { position: relative; min-height: 560px; }
.canvas-toolbar {
  display: flex; gap: 8px; flex-wrap: wrap;
  margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid var(--border-default);
}
.graph-loading {
  position: absolute; inset: 48px 0 0; z-index: 2;
  display: grid; place-items: center; background: rgb(255 255 255 / 70%);
}
.graph-loading .spin { font-size: 28px; color: var(--brand-primary); animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.graph-side-wrap { display: flex; flex-direction: column; gap: 12px; }
.graph-side { overflow: visible; }
.graph-side h4 { margin: 0 0 10px; font-size: 15px; }
.name-list { display: flex; flex-direction: column; gap: 2px; }
.name-item {
  padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 13px;
  line-height: 1.4; word-break: break-all;
}
.name-item:hover { background: #fafaf9; }
.name-item.active { background: #fff7ed; color: #ea580c; }
.detail-dl { margin: 0 0 16px; }
.detail-dl dt { font-size: 12px; color: #64748b; margin-top: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
.detail-dl dt:first-child { margin-top: 0; }
.detail-dl dd { margin: 4px 0 0; font-size: 14px; color: #1e293b; word-break: break-all; line-height: 1.5; }
.detail-dl .mono { font-family: ui-monospace, monospace; font-size: 11px; color: #94a3b8; background: #f8fafc; padding: 2px 6px; border-radius: 4px; }
.detail-section { margin: 20px 0 10px; font-size: 13px; font-weight: 600; color: #334155; display: flex; align-items: center; gap: 8px; }
.detail-section::after { content: ''; flex: 1; height: 1px; background: #e2e8f0; }
.rel-mini { list-style: none; margin: 0; padding: 0; background: #f8fafc; border-radius: 8px; overflow: hidden; }
.rel-mini li {
  padding: 10px 12px; border-bottom: 1px solid #e2e8f0; cursor: pointer; font-size: 13px;
  display: flex; align-items: center; gap: 8px; transition: background 0.15s;
}
.rel-mini li:last-child { border-bottom: none; }
.rel-mini li:hover { background: #fff7ed; color: #f97316; }
.rel-type { margin-left: auto; font-size: 11px; color: #94a3b8; background: #fff; padding: 2px 8px; border-radius: 10px; border: 1px solid #e2e8f0; }
.full-btn { width: 100%; margin-top: 20px; }
.drawer-content { padding: 4px 0; }
.info-card { background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark)); color: #fff; border-radius: var(--radius-md); padding: 16px; margin-bottom: 16px; }
.info-card .info-label { font-size: 11px; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.5px; }
.info-card .info-value { font-size: 16px; font-weight: 600; margin-top: 4px; word-break: break-all; }
.info-item { background: #f8fafc; border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; }
.info-item dt { color: #64748b !important; margin-top: 0 !important; }
.info-item dd { color: #1e293b !important; font-size: 13px !important; }
.relation-flow { display: flex; align-items: center; gap: 12px; padding: 14px; background: linear-gradient(135deg, #f8fafc 0%, #fafaf9 100%); border-radius: 10px; margin-bottom: 16px; }
.relation-flow .node { flex: 1; text-align: center; padding: 10px; background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.relation-flow .node-name { font-size: 13px; font-weight: 500; color: #1e293b; cursor: pointer; }
.relation-flow .node-name:hover { color: #f97316; text-decoration: underline; }
.relation-flow .node-label { font-size: 10px; color: #94a3b8; margin-top: 4px; }
.relation-flow .arrow { font-size: 20px; color: #94a3b8; }
.rel-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.rel-tag { font-size: 12px; padding: 4px 10px; border-radius: 6px; }
.rel-tag.type { background: #fff7ed; color: #f97316; }
.rel-tag.desc { background: #f0fdf4; color: #16a34a; }
.mt { margin-top: 16px; }
.community-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.community-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
.community-card .title { font-weight: 600; margin-bottom: 8px; }
.community-card p { margin: 0; font-size: 13px; color: #475569; }
@media (max-width: 960px) { .graph-layout { grid-template-columns: 1fr; } }
</style>
