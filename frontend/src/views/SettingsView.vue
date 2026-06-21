<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const scopeText = computed(() => (auth.user?.scopes?.length ? auth.user.scopes.join('、') : '—'))
</script>

<template>
  <div>
    <p class="page-desc">账号与平台接入配置</p>

    <div class="card-panel settings-block">
      <h3>当前账号</h3>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="邮箱">{{ auth.user?.email ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="权限范围">{{ scopeText }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="card-panel settings-block">
      <h3>接入说明</h3>
      <ul class="tips">
        <li>前端通过 Vite 代理访问后端 <code>/api</code>，默认指向 <code>localhost:8000</code></li>
        <li>演示账号：<code>seed@demo.com</code> / <code>seed12345</code></li>
        <li>导入测试数据：<code>./scripts/seed_platform_data.py</code></li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
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
}

.tips code {
  font-size: 12px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
