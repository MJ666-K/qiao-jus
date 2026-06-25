<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCaptcha } from '@/api/auth'
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
const captchaKey = ref('')
const captchaImage = ref('')
const captchaCode = ref('')

const heroRef = ref<HTMLElement | null>(null)
const mouseStyle = ref<Record<string, string>>({ '--mx': '25%', '--my': '25%' })

function onHeroMouseMove(e: MouseEvent) {
  const el = heroRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  mouseStyle.value = { '--mx': `${x}%`, '--my': `${y}%` }
}

function onHeroMouseLeave() {
  mouseStyle.value = { '--mx': '25%', '--my': '25%' }
}

async function refreshCaptcha() {
  try {
    const c = await getCaptcha()
    captchaKey.value = c.captcha_key
    captchaImage.value = c.image
    captchaCode.value = ''
  } catch {
    captchaImage.value = ''
  }
}

onMounted(() => {
  refreshCaptcha()
  heroRef.value?.addEventListener('mousemove', onHeroMouseMove)
  heroRef.value?.addEventListener('mouseleave', onHeroMouseLeave)
})

onUnmounted(() => {
  heroRef.value?.removeEventListener('mousemove', onHeroMouseMove)
  heroRef.value?.removeEventListener('mouseleave', onHeroMouseLeave)
})

async function submit() {
  error.value = ''
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value, captchaKey.value, captchaCode.value)
      notifySuccess('登录成功', `欢迎，${auth.user?.email ?? email.value}`)
    } else {
      await auth.register(
        email.value,
        password.value,
        tenantName.value,
        captchaKey.value,
        captchaCode.value,
      )
      notifySuccess('注册成功', '已自动登录')
    }
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (e) {
    const msg = e instanceof Error ? e.message : '操作失败'
    error.value = msg
    notifyError(mode.value === 'login' ? '登录失败' : '注册失败', msg)
    refreshCaptcha()
  }
}
</script>

<template>
  <div class="login-page">
    <aside class="hero" ref="heroRef" :style="mouseStyle">
      <div class="hero-glow hero-glow-a" aria-hidden="true"></div>
      <div class="hero-glow hero-glow-b" aria-hidden="true"></div>
      <div class="hero-glow hero-glow-c" aria-hidden="true"></div>
      <div class="glass-orb glass-orb-1" aria-hidden="true"></div>
      <div class="glass-orb glass-orb-2" aria-hidden="true"></div>
      <div class="hero-brand">
        <div class="logo-badge">枫</div>
        <span class="brand-name">枫桥智诉</span>
      </div>
      <div class="hero-tagline">
        <h1>法律智能辅助平台</h1>
        <p>基于 场景大模型<br />让 AI 依法说话，让普通人看得懂法</p>
      </div>
    </aside>

    <main class="form-panel">
      <div class="form-inner">
        <div class="form-brand">
          <div class="logo-badge">枫</div>
          <span class="brand-name">枫桥智诉</span>
        </div>
        <h2 class="brand-title"><span class="emph">AI</span> 法律智能</h2>

        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="邮箱">
            <el-input v-model="email" type="email" placeholder="请输入邮箱地址" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="password" type="password" show-password placeholder="请输入密码" />
          </el-form-item>
          <el-form-item v-if="mode === 'register'" label="租户名称">
            <el-input v-model="tenantName" placeholder="组织名称" />
          </el-form-item>
          <el-form-item label="验证码">
            <div class="captcha-row">
              <el-input v-model="captchaCode" placeholder="请输入验证码" maxlength="4" />
              <img
                v-if="captchaImage"
                :src="captchaImage"
                class="captcha-img"
                alt="验证码"
                title="点击刷新"
                @click="refreshCaptcha"
              />
              <div v-else class="captcha-placeholder" @click="refreshCaptcha">加载中…</div>
            </div>
          </el-form-item>
          <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="err-alert" />
          <el-button type="primary" native-type="submit" :loading="auth.loading" class="submit-btn">
            {{ mode === 'login' ? '登录' : '注册并登录' }}
          </el-button>
        </el-form>

        <p class="switch-hint">
          {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
          <a class="switch-link" @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === 'login' ? '立即注册' : '立即登录' }}
          </a>
        </p>
      </div>

      <footer class="page-footer">
        <nav class="footer-links">
          <a href="javascript:void(0)">关于我们</a>
          <a href="javascript:void(0)">服务条款</a>
          <a href="javascript:void(0)">隐私政策</a>
        </nav>
        <p class="copyright">© 2026 枫桥智诉 · 法律智能辅助平台</p>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 55fr 45fr;
}

/* ===== 左侧装饰区 ===== */
.hero {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 48px 56px;
  background: var(--brand-bg);
}

.hero-glow {
  position: absolute;
  border-radius: 50%;
  left: var(--mx, 30%);
  top: var(--my, 40%);
  transform: translate(-50%, -50%);
  transition: left 0.25s ease-out, top 0.25s ease-out;
  pointer-events: none;
  z-index: 0;
}

.hero-glow-a {
  width: 560px;
  height: 560px;
  background: radial-gradient(circle, rgba(110, 231, 183, 0.62), transparent 68%);
  filter: blur(8px);
  margin-left: -90px;
  margin-top: 70px;
  animation: drift-a 9s ease-in-out infinite;
}

.hero-glow-b {
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, rgba(251, 113, 133, 0.58), transparent 68%);
  filter: blur(8px);
  margin-left: 100px;
  margin-top: 80px;
  animation: drift-b 11s ease-in-out infinite;
}

.hero-glow-c {
  width: 420px;
  height: 420px;
  background: radial-gradient(circle, rgba(253, 186, 116, 0.55), transparent 68%);
  filter: blur(6px);
  margin-left: 20px;
  margin-top: -90px;
  animation: drift-c 7s ease-in-out infinite;
}

@keyframes drift-a {
  0%, 100% { transform: translate(-50%, -50%); }
  50% { transform: translate(-32%, -68%); }
}

@keyframes drift-b {
  0%, 100% { transform: translate(-50%, -50%); }
  50% { transform: translate(-68%, -34%); }
}

@keyframes drift-c {
  0%, 100% { transform: translate(-50%, -50%); }
  50% { transform: translate(-56%, -22%); }
}

.hero-brand,
.hero-tagline {
  position: relative;
  z-index: 1;
}

.hero-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-badge {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  display: grid;
  place-items: center;
  box-shadow: 0 4px 12px rgb(249 115 22 / 30%);
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.hero-tagline {
  max-width: 440px;
}

.hero-tagline h1 {
  margin: 0 0 18px;
  font-size: 40px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.5px;
  color: var(--text-primary);
}

.hero-tagline p {
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
  color: #6b7280;
}

.glass-orb {
  position: absolute;
  border-radius: 50%;
  background: rgb(255 255 255 / 22%);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgb(255 255 255 / 45%);
  box-shadow: 0 8px 32px rgb(31 41 55 / 8%);
  pointer-events: none;
  z-index: 1;
}

.glass-orb-1 {
  width: 200px;
  height: 200px;
  top: 22%;
  right: 12%;
}

.glass-orb-2 {
  width: 130px;
  height: 130px;
  bottom: 32%;
  left: 18%;
}

/* ===== 右侧表单区 ===== */
.form-panel {
  position: relative;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.form-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  width: 100%;
  max-width: 420px;
  margin: 0 auto;
  padding: 40px 40px 20px;
}

.form-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.form-brand .brand-name {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
}

.brand-title {
  margin: 0 0 20px;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.emph {
  color: #f97316;
  font-style: italic;
}

/* ===== 表单 ===== */
.err-alert {
  margin-bottom: 14px;
}

:deep(.el-form-item) {
  margin-bottom: 14px;
}

.captcha-row {
  display: flex;
  gap: 10px;
  width: 100%;
  align-items: center;
}

.captcha-row :deep(.el-input) {
  flex: 1;
  min-width: 0;
}

.captcha-img {
  height: 44px;
  width: 120px;
  border-radius: 12px;
  cursor: pointer;
  border: 1px solid #e5e7eb;
  flex-shrink: 0;
  object-fit: cover;
}

.captcha-placeholder {
  height: 44px;
  width: 120px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  display: grid;
  place-items: center;
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
  flex-shrink: 0;
}

.submit-btn {
  width: 100%;
  height: 48px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #fb923c, #f97316);
  border: none;
  box-shadow: 0 4px 12px rgb(249 115 22 / 30%);
  transition: all 0.2s;
}

.submit-btn:hover,
.submit-btn:focus {
  background: linear-gradient(135deg, #fb923c, #ea580c);
  box-shadow: 0 2px 8px rgb(249 115 22 / 18%);
  transform: translateY(-1px);
}

:deep(.el-input__wrapper) {
  border-radius: 12px;
  padding: 6px 14px;
  box-shadow: 0 0 0 1px #e5e7eb inset;
  transition: box-shadow 0.2s;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #d1d5db inset;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #f97316 inset, 0 0 0 3px rgb(249 115 22 / 12%);
}

:deep(.el-input__inner) {
  height: 44px;
  font-size: 15px;
}

:deep(.el-form-item__label) {
  color: #4b5563;
  font-weight: 500;
  font-size: 14px;
  padding-bottom: 4px;
}

.switch-hint {
  margin: 16px 0 0;
  text-align: center;
  font-size: 14px;
  color: #6b7280;
}

.switch-link {
  color: #f97316;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  margin-left: 4px;
}

.switch-link:hover {
  color: #ea580c;
}

/* ===== 页脚 ===== */
.page-footer {
  padding: 16px 40px 24px;
  text-align: center;
}

.footer-links {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 8px;
}

.footer-links a {
  color: #6b7280;
  text-decoration: none;
  font-size: 13px;
  transition: color 0.15s;
}

.footer-links a:hover {
  color: #f97316;
}

.copyright {
  margin: 0;
  font-size: 12px;
  color: #9ca3af;
}

/* ===== 移动端 ===== */
@media (max-width: 768px) {
  .login-page {
    grid-template-columns: 1fr;
  }
  .hero {
    display: none;
  }
}
</style>
