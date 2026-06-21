<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createDataset, deleteDataset, listDatasets } from '@/api/datasets'
import { DOC_TYPES, docTypeLabel } from '@/constants/docTypes'
import type { Dataset } from '@/types'

const loading = ref(false)
const datasets = ref<Dataset[]>([])
const dialogVisible = ref(false)
const form = ref({ name: '', description: '', doc_type: 'law', scope: 'platform' })

async function load() {
  loading.value = true
  try {
    datasets.value = await listDatasets()
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  await createDataset({
    name: form.value.name.trim(),
    description: form.value.description.trim() || null,
    metadata: { doc_type: form.value.doc_type, scope: form.value.scope },
  })
  dialogVisible.value = false
  form.value = { name: '', description: '', doc_type: 'law', scope: 'platform' }
  ElMessage.success('创建成功')
  await load()
}

async function remove(id: string, name: string) {
  await ElMessageBox.confirm(`确定删除知识库「${name}」？`, '确认', { type: 'warning' })
  await deleteDataset(id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <p class="page-desc">管理法规、类案等平台公共知识库（对应 dataset 维度）</p>
      <el-button type="primary" @click="dialogVisible = true">新建知识库</el-button>
    </div>

    <div v-loading="loading" class="grid">
      <el-empty v-if="!datasets.length" description="暂无知识库，请先创建" />
      <div v-for="ds in datasets" :key="ds.id" class="card-panel dataset-card">
        <div class="head">
          <h3>{{ ds.name }}</h3>
          <el-button link type="danger" @click="remove(ds.id, ds.name)">删除</el-button>
        </div>
        <p class="desc">{{ ds.description || '暂无描述' }}</p>
        <el-tag size="small" type="info">{{ docTypeLabel(String(ds.metadata?.doc_type || '')) }}</el-tag>
        <div class="meta">ID: {{ ds.id.slice(0, 8) }} · {{ new Date(ds.created_at).toLocaleString('zh-CN') }}</div>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="新建知识库" width="420px">
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：劳动法规库" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.doc_type" style="width:100%">
            <el-option v-for="t in DOC_TYPES.filter(x => x.scope==='platform')" :key="t.id" :label="t.label" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.dataset-card h3 {
  margin: 0;
  font-size: 16px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.desc {
  color: #64748b;
  font-size: 14px;
  min-height: 40px;
}

.meta {
  margin-top: 12px;
  font-size: 12px;
  color: #94a3b8;
}
</style>
