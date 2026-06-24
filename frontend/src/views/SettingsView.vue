<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { listUsers, updateUserRole } from '@/api/auth'
import { getChunkingConfig, updateChunkingConfig, type ChunkingConfig } from '@/api/settings'
import type { User } from '@/types'

const auth = useAuthStore()
const activeTab = ref('account')
const isAdmin = computed(() => auth.user?.role === 'admin')

// ===== User Management =====
const users = ref<User[]>([])
const loadingUsers = ref(false)

async function loadUsers() {
  if (!isAdmin.value) return
  loadingUsers.value = true
  try {
    users.value = await listUsers()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载用户列表失败')
  } finally {
    loadingUsers.value = false
  }
}

async function toggleRole(u: User) {
  const newRole = u.role === 'admin' ? 'user' : 'admin'
  try {
    await updateUserRole(u.id, { role: newRole })
    u.role = newRole
    ElMessage.success(`${u.email} 角色已变更为：${newRole === 'admin' ? '管理员' : '普通用户'}`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '修改失败')
  }
}

// ===== Chunking Rules =====
const chunkingConfig = ref<ChunkingConfig | null>(null)
const savingChunking = ref(false)

async function loadChunkingConfig() {
  try {
    chunkingConfig.value = await getChunkingConfig()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载配置失败')
  }
}

async function saveChunkingConfig() {
  if (!chunkingConfig.value) return
  savingChunking.value = true
  try {
    await updateChunkingConfig(chunkingConfig.value)
    ElMessage.success('切块规则已保存（对后续新上传文档生效）')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    savingChunking.value = false
  }
}

onMounted(() => {
  if (isAdmin.value) {
    loadUsers()
    loadChunkingConfig()
  }
})
</script>

<template>
  <div>
    <p class="page-desc">系统配置 · 账号、用户管理、文本切块规则</p>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <el-tab-pane label="当前账号" name="account">
        <div class="card-panel settings-block">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="邮箱">{{ auth.user?.email ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="显示名">{{ auth.user?.display_name || '未设置' }}</el-descriptions-item>
            <el-descriptions-item label="角色">
              <el-tag :type="isAdmin ? 'danger' : 'primary'" size="small">
                {{ isAdmin ? '管理员' : '普通用户' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="权限">{{ auth.user?.scopes?.join('、') || '—' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="card-panel settings-block">
          <h3>角色说明</h3>
          <ul class="tips">
            <li><strong>普通用户</strong>：可上传文档、生成报告、智能问答（默认角色）</li>
            <li><strong>管理员</strong>：额外可管理平台知识库、检索测试、图谱、用户管理、系统配置</li>
            <li>注册即默认为普通用户；需管理员在「用户管理」标签页中切换角色</li>
          </ul>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isAdmin" label="用户管理" name="users">
        <div v-loading="loadingUsers" class="card-panel">
          <el-table :data="users" stripe>
            <el-table-column prop="email" label="邮箱" min-width="200" />
            <el-table-column prop="display_name" label="显示名" width="120">
              <template #default="{ row }">{{ row.display_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="角色" width="120">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small">
                  {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button
                  size="small"
                  :type="row.role === 'admin' ? 'warning' : 'primary'"
                  link
                  @click="toggleRole(row)"
                >
                  {{ row.role === 'admin' ? '降为普通用户' : '提升为管理员' }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isAdmin" label="文本切块规则" name="chunking">
        <div v-if="chunkingConfig" class="card-panel settings-block">
          <h3>切块与检索参数</h3>
          <el-form label-width="200px" label-position="right">
            <el-form-item label="父块大小 (tokens)">
              <el-input-number v-model="chunkingConfig.chunk_parent_tokens" :min="200" :max="4000" :step="100" />
            </el-form-item>
            <el-form-item label="子块大小 (tokens)">
              <el-input-number v-model="chunkingConfig.chunk_child_tokens" :min="50" :max="2000" :step="50" />
            </el-form-item>
            <el-form-item label="重叠 (tokens)">
              <el-input-number v-model="chunkingConfig.chunk_overlap_tokens" :min="0" :max="200" :step="10" />
            </el-form-item>
            <el-divider>检索参数</el-divider>
            <el-form-item label="Top-K 召回">
              <el-input-number v-model="chunkingConfig.search_top_k" :min="1" :max="50" />
            </el-form-item>
            <el-form-item label="RRF K 值">
              <el-input-number v-model="chunkingConfig.rrf_k" :min="1" :max="200" />
            </el-form-item>
            <el-form-item label="Rerank Top-K">
              <el-input-number v-model="chunkingConfig.rerank_top_k" :min="5" :max="100" />
            </el-form-item>
            <el-divider>BM25 与混合检索</el-divider>
            <el-form-item label="BM25 k1（词频饱和度）">
              <el-input-number v-model="chunkingConfig.bm25_k1" :min="0" :max="3" :step="0.1" />
            </el-form-item>
            <el-form-item label="BM25 b（文档长度归一）">
              <el-input-number v-model="chunkingConfig.bm25_b" :min="0" :max="1" :step="0.05" />
            </el-form-item>
            <el-form-item label="Dense/BM25 召回扩展倍数">
              <el-input-number v-model="chunkingConfig.dense_top_k_multiplier" :min="1" :max="10" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingChunking" @click="saveChunkingConfig">保存配置</el-button>
              <span class="hint">仅对后续新上传文档生效；存量文档需重新索引</span>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.settings-tabs {
  margin-bottom: 16px;
}

.settings-block h3 {
  margin: 0 0 16px;
  font-size: 16px;
}

.settings-block + .settings-block {
  margin-top: 16px;
}

.tips {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
  color: #475569;
  font-size: 14px;
}

.hint {
  margin-left: 12px;
  color: #94a3b8;
  font-size: 12px;
}
</style>
