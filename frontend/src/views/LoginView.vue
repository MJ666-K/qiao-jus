<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { notifyError, notifySuccess } from '@/utils/notify'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('seed@demo.com')
const password = ref('seed12345')
const tenantName = ref('demo')
const mode = ref<'login' | 'register'>('login')
const error = ref('')

async function submit() {
  error.value = ''
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value)
      notifySuccess('登录成功', `欢迎，${auth.user?.email ?? email.value}`)
    } else {
      await auth.register(email.value, password.value, tenantName.value)
      notifySuccess('注册成功', '已自动登录')
    }
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (e) {
    const msg = e instanceof Error ? e.message : '操作失败'
    error.value = msg
    notifyError(mode.value === 'login' ? '登录失败' : '注册失败', msg)
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="hero">
        <h1>枫桥智诉智能体</h1>
        <p>基于 RAG + 知识图谱的法规/类案知识底座</p>
        <ul>
          <li>Hybrid 检索：向量 + BM25 + RRF</li>
          <li>GraphRAG：实体关系 + 社区摘要</li>
          <li>多租户隔离，模块化 Skill 架构</li>
        </ul>
      </div>

      <div class="form-panel">
        <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>
        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="邮箱">
            <el-input v-model="email" type="email" placeholder="seed@demo.com" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="password" type="password" show-password placeholder="seed12345" />
          </el-form-item>
          <el-form-item v-if="mode === 'register'" label="租户名称">
            <el-input v-model="tenantName" placeholder="组织名称" />
          </el-form-item>
          <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="mb" />
          <el-button type="primary" native-type="submit" :loading="auth.loading" class="full">
            {{ mode === 'login' ? '登录' : '注册并登录' }}
          </el-button>
          <el-button link @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === 'login' ? '没有账号？注册' : '已有账号？登录' }}
          </el-button>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 50%, #ede9fe 100%);
  padding: 24px;
}

.login-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  max-width: 920px;
  width: 100%;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 50px rgb(15 23 42 / 12%);
}

.hero {
  padding: 48px 40px;
  background: linear-gradient(160deg, #1e3a8a, #4338ca);
  color: #fff;
}

.hero h1 {
  margin: 0 0 8px;
  font-size: 28px;
}

.hero p {
  margin: 0 0 24px;
  opacity: 0.9;
}

.hero ul {
  margin: 0;
  padding-left: 18px;
  line-height: 1.9;
  opacity: 0.95;
}

.form-panel {
  padding: 48px 40px;
}

.form-panel h2 {
  margin: 0 0 24px;
}

.full {
  width: 100%;
  margin-bottom: 8px;
}

.mb {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .login-card {
    grid-template-columns: 1fr;
  }
  .hero {
    display: none;
  }
}
</style>
