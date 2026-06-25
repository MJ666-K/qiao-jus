<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Avatar,
  ChatDotRound,
  Collection,
  Document,
  DArrowLeft,
  DArrowRight,
  MoreFilled,
  Plus,
} from "@element-plus/icons-vue";
import {
  createAssistant,
  deleteAssistant,
  listAssistants,
  updateAssistant,
} from "@/api/assistants";
import {
  deleteConversation,
  getConversation,
  listConversations,
  updateConversation,
} from "@/api/conversations";
import { listReports } from "@/api/reports";
import { useConversationStore } from "@/stores/conversation";
import { useKnowledgeContextStore } from "@/stores/knowledgeContext";
import type {
  AssistantSummary,
  ConversationSummary,
  Report,
  SourceType,
} from "@/types";
import { marked } from "marked";

marked.setOptions({ breaks: true, gfm: true });

const route = useRoute();
const router = useRouter();
const store = useConversationStore();
const kb = useKnowledgeContextStore();

const inputText = ref("");
const assistants = ref<AssistantSummary[]>([]);
const conversations = ref<ConversationSummary[]>([]);
const reportOptions = ref<Report[]>([]);
const scrollContainer = ref<HTMLDivElement | null>(null);

const assistantDialogVisible = ref(false);
const assistantDialogMode = ref<"new" | "edit">("new");
const editingAssistantId = ref<string | null>(null);
const assistantFormName = ref("");
const assistantFormDesc = ref("");
const assistantFormDatasetIds = ref<string[]>([]);
const assistantFormReportIds = ref<string[]>([]);

const convDialogVisible = ref(false);
const convDialogMode = ref<"edit">("edit");
const editingConvId = ref<string | null>(null);
const convFormTitle = ref("");

const assistantCollapsed = ref(false);
const convCollapsed = ref(false);

const selectedAssistantId = computed(
  () => (route.params.assistantId as string) || null,
);
const selectedConversationId = computed(
  () => (route.params.conversationId as string) || null,
);

const currentAssistant = computed(() =>
  assistants.value.find((a) => a.id === selectedAssistantId.value) ?? null,
);

const groupedConversations = computed(() => {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
  const groups: { label: string; conversations: ConversationSummary[] }[] = [
    { label: "今日", conversations: [] },
    { label: "七日内", conversations: [] },
    { label: "一个月内", conversations: [] },
    { label: "更早", conversations: [] },
  ];
  for (const conv of conversations.value) {
    const d = new Date(conv.updated_at);
    if (d >= today) groups[0].conversations.push(conv);
    else if (d >= weekAgo) groups[1].conversations.push(conv);
    else if (d >= monthAgo) groups[2].conversations.push(conv);
    else groups[3].conversations.push(conv);
  }
  return groups.filter((g) => g.conversations.length > 0);
});

function renderMarkdown(content: string): string {
  return marked.parse(content) as string;
}

const sourceTagType: Record<
  SourceType,
  "success" | "warning" | "info" | "primary" | "danger"
> = {
  law: "primary",
  case: "success",
  report: "warning",
  user_doc: "info",
  compliance: "primary",
  graph: "danger",
};

const sourceTagText: Record<SourceType, string> = {
  law: "法规",
  case: "类案",
  report: "报告",
  user_doc: "材料",
  compliance: "合规",
  graph: "图谱",
};

function assistantInitial(name: string) {
  return (name.trim().charAt(0) || "助").toUpperCase();
}

const avatarColors = ["#f97316", "#3b82f6", "#10b981", "#8b5cf6", "#0ea5e9", "#ec4899"];

function assistantColor(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash += id.charCodeAt(i);
  return avatarColors[hash % avatarColors.length];
}

async function loadAssistants() {
  try {
    assistants.value = await listAssistants();
  } catch {
    assistants.value = [];
  }
}

async function loadConversations() {
  if (!selectedAssistantId.value) {
    conversations.value = [];
    return;
  }
  try {
    conversations.value = await listConversations(selectedAssistantId.value);
  } catch {
    conversations.value = [];
  }
}

async function loadReportOptions() {
  try {
    reportOptions.value = await listReports();
  } catch {
    reportOptions.value = [];
  }
}

function navigateToAssistant(assistantId: string, conversationId?: string) {
  if (conversationId) {
    router.push({
      name: "assistant-chat",
      params: { assistantId, conversationId },
    });
  } else {
    router.push({ name: "assistant-home", params: { assistantId } });
  }
}

async function selectAssistant(a: AssistantSummary) {
  navigateToAssistant(a.id);
  assistantCollapsed.value = true;
}

watch(
  () => selectedAssistantId.value,
  (id, oldId) => {
    if (id) assistantCollapsed.value = true;
    else assistantCollapsed.value = false;
    if (id && id !== oldId) convCollapsed.value = false;
  },
);

const currentConversationTitle = computed(() => {
  if (store.currentConversation?.title) return store.currentConversation.title;
  const conv = conversations.value.find((c) => c.id === selectedConversationId.value);
  return conv?.title ?? null;
});

async function ensureSession() {
  if (!selectedAssistantId.value) return;
  store.currentAssistantId = selectedAssistantId.value;
  if (selectedConversationId.value) {
    try {
      await store.initConversation({
        assistantId: selectedAssistantId.value,
        conversationId: selectedConversationId.value,
      });
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : "会话连接失败");
    }
  } else {
    store.disconnect();
    store.clearCurrentConversation();
  }
}

function resetAssistantForm() {
  assistantFormName.value = "";
  assistantFormDesc.value = "";
  assistantFormDatasetIds.value = [];
  assistantFormReportIds.value = [];
  editingAssistantId.value = null;
}

function openNewAssistantDialog() {
  assistantDialogMode.value = "new";
  resetAssistantForm();
  const reportIdFromQuery = route.query.report_id as string | undefined;
  if (reportIdFromQuery) {
    assistantFormReportIds.value = [reportIdFromQuery];
  }
  assistantDialogVisible.value = true;
}

function openEditAssistantDialog(a: AssistantSummary) {
  assistantDialogMode.value = "edit";
  editingAssistantId.value = a.id;
  assistantFormName.value = a.name;
  assistantFormDesc.value = a.description || "";
  assistantFormDatasetIds.value = [...(a.dataset_ids || [])];
  assistantFormReportIds.value = [...(a.report_ids || [])];
  assistantDialogVisible.value = true;
}

async function submitAssistantDialog() {
  const name = assistantFormName.value.trim() || "新助手";
  try {
    if (assistantDialogMode.value === "new") {
      const a = await createAssistant({
        name,
        description: assistantFormDesc.value.trim() || undefined,
        dataset_ids: assistantFormDatasetIds.value,
        report_ids: assistantFormReportIds.value,
      });
      await loadAssistants();
      assistantDialogVisible.value = false;
      navigateToAssistant(a.id);
      ElMessage.success("助手已创建");
    } else if (editingAssistantId.value) {
      await updateAssistant(editingAssistantId.value, {
        name,
        description: assistantFormDesc.value.trim() || undefined,
        dataset_ids: assistantFormDatasetIds.value,
        report_ids: assistantFormReportIds.value,
      });
      await loadAssistants();
      assistantDialogVisible.value = false;
      ElMessage.success("已保存");
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "操作失败");
  }
}

async function removeAssistant(a: AssistantSummary) {
  try {
    await ElMessageBox.confirm(
      `删除助手「${a.name}」将同时删除其下所有会话，确认？`,
      "删除助手",
      { type: "warning" },
    );
  } catch {
    return;
  }
  try {
    await deleteAssistant(a.id);
    if (selectedAssistantId.value === a.id) {
      store.disconnect();
      store.clearCurrentConversation();
      router.push({ name: "assistants" });
    }
    await loadAssistants();
    ElMessage.success("已删除");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "删除失败");
  }
}

async function startNewConversation() {
  if (!selectedAssistantId.value) {
    ElMessage.warning("请先选择助手");
    return;
  }
  try {
    const conv = await store.createConversationAndConnect(selectedAssistantId.value);
    await loadConversations();
    navigateToAssistant(selectedAssistantId.value, conv.id);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "创建会话失败");
  }
}

async function switchConversation(conv: ConversationSummary) {
  if (!selectedAssistantId.value) return;
  navigateToAssistant(selectedAssistantId.value, conv.id);
}

function openEditConversationDialog(conv: ConversationSummary) {
  convDialogMode.value = "edit";
  editingConvId.value = conv.id;
  convFormTitle.value = conv.title;
  convDialogVisible.value = true;
}

async function submitConvDialog() {
  if (!editingConvId.value) return;
  try {
    const updated = await updateConversation(editingConvId.value, {
      title: convFormTitle.value.trim() || "新对话",
    });
    const idx = conversations.value.findIndex((c) => c.id === editingConvId.value);
    if (idx >= 0) {
      conversations.value[idx] = { ...conversations.value[idx], title: updated.title };
    }
    convDialogVisible.value = false;
    ElMessage.success("已保存");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  }
}

async function removeConversation(conv: ConversationSummary) {
  try {
    await ElMessageBox.confirm(`确认删除会话「${conv.title}」？`, "删除会话", {
      type: "warning",
    });
  } catch {
    return;
  }
  try {
    await deleteConversation(conv.id);
    if (store.currentConversation?.id === conv.id) {
      store.disconnect();
      store.clearCurrentConversation();
      if (selectedAssistantId.value) {
        router.push({ name: "assistant-home", params: { assistantId: selectedAssistantId.value } });
      }
    }
    await loadConversations();
    ElMessage.success("已删除");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "删除失败");
  }
}

async function send() {
  const text = inputText.value.trim();
  if (!text || !selectedAssistantId.value) return;
  inputText.value = "";
  await store.sendMessage(text);
  await scrollToBottom();
  await loadConversations();
  if (store.currentConversation && !selectedConversationId.value) {
    navigateToAssistant(selectedAssistantId.value, store.currentConversation.id);
  }
}

function pickSuggested(q: string) {
  inputText.value = q;
  send();
}

async function scrollToBottom() {
  await nextTick();
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
  }
}

async function handleLegacyChatRedirect() {
  const legacyConvId = route.params.conversationId as string | undefined;
  if (!legacyConvId || route.name !== "chat-legacy") return;
  try {
    const conv = await getConversation(legacyConvId);
    router.replace({
      name: "assistant-chat",
      params: { assistantId: conv.assistant_id, conversationId: conv.id },
    });
  } catch {
    router.replace({ name: "assistants" });
  }
}

watch(() => store.streamingMessage, () => scrollToBottom());
watch(() => store.messages.length, () => scrollToBottom());

watch(
  () => [route.params.assistantId, route.params.conversationId],
  async () => {
    await loadConversations();
    if (!store.isStreaming) await ensureSession();
  },
);

onMounted(async () => {
  await handleLegacyChatRedirect();
  await Promise.all([loadAssistants(), loadReportOptions(), kb.loadDatasets()]);
  if (route.name === "assistants" && assistants.value.length && !selectedAssistantId.value) {
    navigateToAssistant(assistants.value[0].id);
    return;
  }
  await loadConversations();
  await ensureSession();
});

onUnmounted(() => store.disconnect());
</script>

<template>
  <div class="chat-page">
    <!-- 助手列表 -->
    <aside class="panel assistant-panel" :class="{ 'is-collapsed': assistantCollapsed }">
      <div v-if="assistantCollapsed" class="panel-rail">
        <button
          type="button"
          class="rail-btn"
          title="展开助手列表"
          @click="assistantCollapsed = false"
        >
          <el-icon><DArrowRight /></el-icon>
        </button>
        <button
          type="button"
          class="rail-btn rail-btn--accent"
          title="新建助手"
          @click="openNewAssistantDialog"
        >
          <el-icon><Plus /></el-icon>
        </button>
        <div class="rail-divider" />
        <button
          v-for="a in assistants"
          :key="a.id"
          type="button"
          class="rail-avatar"
          :class="{ active: selectedAssistantId === a.id }"
          :style="{ background: assistantColor(a.id) }"
          :title="a.name"
          @click="selectAssistant(a)"
        >
          {{ assistantInitial(a.name) }}
        </button>
      </div>

      <template v-else>
        <div class="panel-head">
          <div class="panel-head-text">
            <span class="panel-label">助手</span>
            <span class="panel-count">{{ assistants.length }}</span>
          </div>
          <div class="panel-head-actions">
            <el-button
              class="head-btn"
              type="primary"
              size="small"
              :icon="Plus"
              round
              @click="openNewAssistantDialog"
            >
              新建
            </el-button>
            <button
              type="button"
              class="collapse-btn"
              title="收起"
              @click="assistantCollapsed = true"
            >
              <el-icon><DArrowLeft /></el-icon>
            </button>
          </div>
        </div>

        <div class="panel-body">
          <button
            v-if="!assistants.length"
            type="button"
            class="create-card"
            @click="openNewAssistantDialog"
          >
            <span class="create-card-icon">+</span>
            <span class="create-card-title">创建第一个助手</span>
            <span class="create-card-desc">绑定知识库与报告，开始智能对话</span>
          </button>

          <div
            v-for="a in assistants"
            :key="a.id"
            class="nav-card"
            :class="{ active: selectedAssistantId === a.id }"
            @click="selectAssistant(a)"
          >
            <div class="nav-card-avatar" :style="{ background: assistantColor(a.id) }">
              {{ assistantInitial(a.name) }}
            </div>
            <div class="nav-card-body">
              <div class="nav-card-title">{{ a.name }}</div>
              <div class="nav-card-tags">
                <span v-if="a.dataset_ids?.length" class="tag tag-db">
                  <el-icon><Collection /></el-icon>{{ a.dataset_ids.length }} 库
                </span>
                <span v-if="a.report_ids?.length" class="tag tag-rpt">
                  <el-icon><Document /></el-icon>{{ a.report_ids.length }} 报告
                </span>
                <span
                  v-if="!a.dataset_ids?.length && !a.report_ids?.length"
                  class="tag tag-plain"
                >
                  直接对话
                </span>
              </div>
            </div>
            <el-dropdown trigger="click" @click.stop>
              <el-icon class="more-btn" @click.stop><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click.stop="openEditAssistantDialog(a)">编辑</el-dropdown-item>
                  <el-dropdown-item @click.stop="removeAssistant(a)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>
    </aside>

    <!-- 会话列表 -->
    <aside
      v-if="selectedAssistantId"
      class="panel conv-panel"
      :class="{ 'is-collapsed': convCollapsed }"
    >
      <div v-if="convCollapsed" class="panel-rail">
        <button
          type="button"
          class="rail-btn"
          title="展开会话列表"
          @click="convCollapsed = false"
        >
          <el-icon><DArrowRight /></el-icon>
        </button>
        <button
          type="button"
          class="rail-btn rail-btn--accent"
          title="新建会话"
          @click="startNewConversation"
        >
          <el-icon><Plus /></el-icon>
        </button>
        <div class="rail-divider" />
        <button
          v-for="conv in conversations"
          :key="conv.id"
          type="button"
          class="rail-dot"
          :class="{ active: selectedConversationId === conv.id }"
          :title="conv.title"
          @click="switchConversation(conv)"
        />
      </div>

      <template v-else>
        <div class="panel-head">
          <div class="panel-head-text">
            <span class="panel-label">会话</span>
            <span class="panel-count">{{ conversations.length }}</span>
          </div>
          <div class="panel-head-actions">
            <el-button
              class="head-btn"
              type="primary"
              size="small"
              :icon="Plus"
              round
              @click="startNewConversation"
            >
              新建
            </el-button>
            <button type="button" class="collapse-btn" title="收起" @click="convCollapsed = true">
              <el-icon><DArrowLeft /></el-icon>
            </button>
          </div>
        </div>

        <div v-if="currentAssistant" class="context-strip">
          <span
            class="context-avatar"
            :style="{ background: assistantColor(currentAssistant.id) }"
          >
            {{ assistantInitial(currentAssistant.name) }}
          </span>
          <span class="context-name">{{ currentAssistant.name }}</span>
        </div>

        <div class="panel-body panel-body--conv">
          <button
            v-if="!conversations.length"
            type="button"
            class="create-card create-card--sm"
            @click="startNewConversation"
          >
            <span class="create-card-icon">+</span>
            <span class="create-card-title">新建会话</span>
          </button>

          <template v-else>
            <div v-for="group in groupedConversations" :key="group.label" class="conv-group">
              <div class="group-label">{{ group.label }}</div>
              <div
                v-for="conv in group.conversations"
                :key="conv.id"
                class="nav-card nav-card--conv"
                :class="{ active: selectedConversationId === conv.id }"
                @click="switchConversation(conv)"
              >
                <div class="nav-card-body">
                  <div class="nav-card-title">{{ conv.title }}</div>
                  <div class="nav-card-meta">
                    {{
                      new Date(conv.updated_at).toLocaleString("zh-CN", {
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    }}
                  </div>
                </div>
                <el-dropdown trigger="click" @click.stop>
                  <el-icon class="more-btn" @click.stop><MoreFilled /></el-icon>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click.stop="openEditConversationDialog(conv)">
                        编辑
                      </el-dropdown-item>
                      <el-dropdown-item @click.stop="removeConversation(conv)">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </template>
        </div>
      </template>
    </aside>

    <!-- 对话区 -->
    <section class="panel chat-panel">
      <div v-if="!selectedAssistantId" class="welcome">
        <div class="welcome-card">
          <div class="welcome-icon">
            <el-icon><Avatar /></el-icon>
          </div>
          <h2 class="welcome-title">欢迎使用我的助手</h2>
          <p class="welcome-desc">
            创建专属助手，绑定知识库与报告；在助手下开启多个会话，专注不同问题。
          </p>
          <el-button type="primary" size="large" round @click="openNewAssistantDialog">
            创建助手
          </el-button>
        </div>
      </div>

      <template v-else>
        <header v-if="currentAssistant" class="chat-header">
          <div class="chat-header-main">
            <div class="chat-header-toggles">
              <button
                v-if="assistantCollapsed"
                type="button"
                class="header-toggle"
                @click="assistantCollapsed = false"
              >
                <el-icon><Avatar /></el-icon>
                <span>助手</span>
              </button>
              <button
                v-if="convCollapsed"
                type="button"
                class="header-toggle"
                @click="convCollapsed = false"
              >
                <el-icon><ChatDotRound /></el-icon>
                <span>会话</span>
              </button>
            </div>
            <div
              class="chat-header-avatar"
              :style="{ background: assistantColor(currentAssistant.id) }"
            >
              {{ assistantInitial(currentAssistant.name) }}
            </div>
            <div class="chat-header-info">
              <h2 class="chat-header-title">
                {{ currentConversationTitle || currentAssistant.name }}
              </h2>
              <p v-if="currentConversationTitle" class="chat-header-sub">
                {{ currentAssistant.name }}
                <template v-if="currentAssistant.report_ids?.length">
                  · {{ currentAssistant.report_ids.length }} 份报告
                </template>
                <template v-else-if="currentAssistant.dataset_ids?.length">
                  · {{ currentAssistant.dataset_ids.length }} 个知识库
                </template>
              </p>
              <p v-else-if="currentAssistant.description" class="chat-header-desc">
                {{ currentAssistant.description }}
              </p>
              <div v-else class="chat-header-tags">
                <span v-if="currentAssistant.dataset_ids?.length" class="header-tag">
                  {{ currentAssistant.dataset_ids.length }} 个知识库
                </span>
                <span v-if="currentAssistant.report_ids?.length" class="header-tag">
                  {{ currentAssistant.report_ids.length }} 份报告
                </span>
                <span
                  v-if="!currentAssistant.dataset_ids?.length && !currentAssistant.report_ids?.length"
                  class="header-tag muted"
                >
                  未绑定资源 · 直接对话
                </span>
              </div>
            </div>
          </div>
        </header>

        <div class="chat-body">
          <div ref="scrollContainer" class="messages">
          <div class="messages-inner">
          <div
            v-if="!store.messages.length && !store.streamingMessage"
            class="chat-empty"
          >
            <el-icon class="chat-empty-icon"><ChatDotRound /></el-icon>
            <p>开始提问吧</p>
            <span class="chat-empty-hint">例如：合同第 2 条风险怎么改？</span>
          </div>

          <div v-for="m in store.messages" :key="m.id" class="msg-row" :class="m.role">
            <div
              v-if="m.role === 'assistant' && currentAssistant"
              class="msg-avatar"
              :style="{ background: assistantColor(currentAssistant.id) }"
            >
              {{ assistantInitial(currentAssistant.name) }}
            </div>
            <div class="bubble">
              <div class="markdown-content" v-html="renderMarkdown(m.content)" />
              <div v-if="m.role === 'assistant'" class="msg-meta">
                <div v-if="m.citations.length" class="citations">
                  <el-collapse>
                    <el-collapse-item :title="`引用来源 (${m.citations.length})`">
                      <div v-for="(c, i) in m.citations" :key="i" class="source-item">
                        <div class="source-title">
                          <el-tag :type="sourceTagType[c.source_type]" size="small">
                            {{ sourceTagText[c.source_type] }}
                          </el-tag>
                          <span class="title-text">{{ c.source_title }}</span>
                        </div>
                        <pre v-if="c.excerpt" class="text-pre excerpt">{{ c.excerpt }}</pre>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </div>
                <div v-if="m.suggested_questions.length" class="suggested">
                  <div class="suggested-label">继续追问</div>
                  <div class="suggested-chips">
                    <button
                      v-for="(q, i) in m.suggested_questions"
                      :key="i"
                      type="button"
                      class="suggested-chip"
                      @click="pickSuggested(q)"
                    >
                      {{ q }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="store.statusMessage && !store.streamingMessage" class="msg-row assistant">
            <div
              v-if="currentAssistant"
              class="msg-avatar"
              :style="{ background: assistantColor(currentAssistant.id) }"
            >
              {{ assistantInitial(currentAssistant.name) }}
            </div>
            <div class="bubble status">
              <div class="thinking-indicator">
                <span class="dot" /><span class="dot" /><span class="dot" />
              </div>
              <span class="status-text">{{ store.statusMessage }}</span>
            </div>
          </div>

          <div v-if="store.streamingMessage" class="msg-row assistant">
            <div
              v-if="currentAssistant"
              class="msg-avatar"
              :style="{ background: assistantColor(currentAssistant.id) }"
            >
              {{ assistantInitial(currentAssistant.name) }}
            </div>
            <div class="bubble streaming">
              <div class="markdown-content" v-html="renderMarkdown(store.streamingMessage)" />
              <span class="cursor">▍</span>
            </div>
          </div>
          </div>
          </div>
        </div>

        <div class="composer">
          <div class="composer-inner">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="2"
              :disabled="store.isStreaming"
              placeholder="输入问题，Ctrl + Enter 发送"
              resize="none"
              @keyup.ctrl.enter="send"
            />
            <div class="composer-actions">
              <el-button
                v-if="store.isStreaming"
                type="danger"
                round
                @click="store.stopGeneration()"
              >
                停止
              </el-button>
              <el-button
                v-else
                type="primary"
                round
                :disabled="!inputText.trim()"
                @click="send"
              >
                发送
              </el-button>
            </div>
          </div>
        </div>
      </template>
    </section>

    <!-- 助手编辑弹窗 -->
    <el-dialog
      v-model="assistantDialogVisible"
      :title="assistantDialogMode === 'new' ? '新建助手' : '编辑助手'"
      width="480px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="助手名称" required>
          <el-input v-model="assistantFormName" placeholder="例如：合同审查助手" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述（可选）">
          <el-input
            v-model="assistantFormDesc"
            type="textarea"
            :rows="2"
            placeholder="简要说明助手用途"
          />
        </el-form-item>
        <el-form-item label="绑定知识库（可多选）">
          <el-select
            v-model="assistantFormDatasetIds"
            multiple
            clearable
            filterable
            placeholder="不选则不做文档召回"
            :loading="kb.loading"
            style="width: 100%"
          >
            <el-option-group v-if="kb.userDatasets.length" label="私有知识库">
              <el-option
                v-for="ds in kb.userDatasets"
                :key="ds.id"
                :label="ds.name"
                :value="ds.id"
              />
            </el-option-group>
            <el-option-group v-if="kb.platformDatasets.length" label="平台公共库">
              <el-option
                v-for="ds in kb.platformDatasets"
                :key="ds.id"
                :label="ds.name"
                :value="ds.id"
              />
            </el-option-group>
          </el-select>
          <p class="form-hint">不绑定知识库时，助手将直接与大模型对话</p>
        </el-form-item>
        <el-form-item label="绑定报告（可多选）">
          <el-select
            v-model="assistantFormReportIds"
            multiple
            clearable
            filterable
            placeholder="可选"
            style="width: 100%"
          >
            <el-option
              v-for="r in reportOptions"
              :key="r.id"
              :label="`${r.type} · ${(r.summary || r.id.slice(0, 8)).slice(0, 30)}`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assistantDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAssistantDialog">
          {{ assistantDialogMode === "new" ? "创建" : "保存" }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 会话编辑弹窗 -->
    <el-dialog v-model="convDialogVisible" title="编辑会话" width="400px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="会话标题">
          <el-input v-model="convFormTitle" maxlength="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="convDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitConvDialog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex: 1;
  height: 100%;
  min-height: 0;
  max-height: 100%;
  background: transparent;
  overflow: hidden;
  gap: 0;
}

.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: rgb(255 255 255 / 78%);
  backdrop-filter: blur(12px);
  border-right: 1px solid rgb(231 229 228 / 70%);
  flex-shrink: 0;
  transition: width 0.22s ease;
  overflow: hidden;
}

.assistant-panel {
  width: 252px;
}

.assistant-panel.is-collapsed {
  width: 52px;
}

.conv-panel {
  width: 236px;
}

.conv-panel.is-collapsed {
  width: 52px;
}

.chat-panel {
  flex: 1;
  min-width: 0;
  min-height: 0;
  border-right: none;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: rgb(255 255 255 / 65%);
  backdrop-filter: blur(16px);
}

/* Collapsed rail */
.panel-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px 8px;
  height: 100%;
  overflow-y: auto;
}

.rail-btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: rgb(255 255 255 / 80%);
  color: var(--text-secondary);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.18s;
  flex-shrink: 0;
}

.rail-btn:hover {
  border-color: var(--brand-primary-light);
  background: #fff;
  color: var(--text-primary);
  box-shadow: var(--shadow-sm);
}

.rail-btn--accent {
  background: var(--brand-primary-soft);
  border-color: var(--brand-primary-light);
  color: var(--brand-primary-dark);
}

.rail-divider {
  width: 20px;
  height: 1px;
  background: var(--border-default);
  margin: 2px 0;
  flex-shrink: 0;
}

.rail-avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  border: 2px solid transparent;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.rail-avatar:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.rail-avatar.active {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px rgb(249 115 22 / 18%);
}

.rail-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d6d3d1;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  transition: background 0.15s, transform 0.15s;
}

.rail-dot:hover {
  background: #a8a29e;
  transform: scale(1.25);
}

.rail-dot.active {
  background: var(--brand-primary);
  transform: scale(1.35);
}

.panel-head-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.collapse-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-default);
  border-radius: 10px;
  background: rgb(255 255 255 / 70%);
  color: var(--text-muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.collapse-btn:hover {
  color: var(--text-secondary);
  border-color: var(--border-strong);
  background: #fff;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 10px;
  flex-shrink: 0;
}

.panel-head-text {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.panel-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.panel-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--border-subtle);
  padding: 2px 8px;
  border-radius: 999px;
}

.head-btn {
  --el-button-size: 28px;
  font-size: 12px;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.panel-body--conv {
  padding-top: 6px;
}

.create-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 22px 14px;
  border: 1.5px dashed var(--border-strong);
  border-radius: var(--radius-md);
  background: rgb(255 255 255 / 50%);
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.create-card:hover {
  border-color: var(--brand-primary);
  background: var(--brand-primary-soft);
  box-shadow: var(--shadow-sm);
}

.create-card--sm {
  padding: 16px 12px;
}

.create-card-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--brand-gradient);
  color: #fff;
  font-size: 22px;
  line-height: 40px;
  font-weight: 300;
  box-shadow: var(--shadow-brand);
}

.create-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.create-card-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.nav-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.nav-card:hover {
  background: rgb(255 255 255 / 85%);
  box-shadow: var(--shadow-sm);
}

.nav-card.active {
  background: var(--brand-primary-soft);
  border-color: var(--brand-primary-light);
  box-shadow: 0 2px 8px rgb(249 115 22 / 10%);
}

.nav-card--conv {
  gap: 0;
}

.nav-card-avatar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  box-shadow: 0 4px 10px rgb(28 25 23 / 12%);
}

.nav-card-body {
  flex: 1;
  min-width: 0;
  padding-right: 18px;
}

.nav-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.nav-card.active .nav-card-title {
  color: var(--brand-primary-dark);
}

.nav-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 6px;
  font-weight: 500;
}

.tag .el-icon {
  font-size: 11px;
}

.tag-db {
  background: #eff6ff;
  color: #2563eb;
}

.tag-rpt {
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
}

.tag-plain {
  background: var(--border-subtle);
  color: var(--text-secondary);
}

.nav-card-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.more-btn {
  position: absolute;
  top: 10px;
  right: 8px;
  font-size: 14px;
  color: var(--border-strong);
  opacity: 0;
  transform: rotate(90deg);
  transition: all 0.15s;
  cursor: pointer;
}

.nav-card:hover .more-btn {
  opacity: 1;
  color: var(--text-muted);
}

.context-strip {
  margin: 0 10px 6px;
  padding: 8px 12px;
  background: rgb(255 255 255 / 70%);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.context-avatar {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.context-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  padding: 10px 6px 6px;
}

.conv-group + .conv-group {
  margin-top: 2px;
}

/* Welcome */
.welcome {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  overflow: hidden;
}

.welcome-card {
  text-align: center;
  max-width: 400px;
  padding: 40px 36px;
  background: rgb(255 255 255 / 85%);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
}

.welcome-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  border-radius: 20px;
  background: var(--brand-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  color: #fff;
  box-shadow: var(--shadow-brand);
}

.welcome-title {
  margin: 0 0 10px;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.welcome-desc {
  margin: 0 0 24px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-body);
}

/* Chat header */
.chat-header {
  padding: 14px 24px;
  border-bottom: 1px solid rgb(231 229 228 / 60%);
  background: rgb(255 255 255 / 55%);
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}

.chat-header-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  max-width: 820px;
  margin: 0 auto;
}

.chat-header-toggles {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.header-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  background: rgb(255 255 255 / 80%);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.header-toggle:hover {
  border-color: var(--brand-primary-light);
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
}

.chat-header-info {
  min-width: 0;
  flex: 1;
}

.chat-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgb(28 25 23 / 14%);
}

.chat-header-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  letter-spacing: -0.2px;
}

.chat-header-sub {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-header-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.5;
}

.chat-header-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.header-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--border-subtle);
  color: var(--text-secondary);
  font-weight: 500;
}

.header-tag.muted {
  color: var(--text-muted);
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: var(--text-muted);
  flex: 1;
}

.chat-empty-icon {
  font-size: 52px;
  color: var(--brand-primary-light);
  margin-bottom: 14px;
}

.chat-empty p {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-secondary);
}

.chat-empty-hint {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-muted);
  padding: 6px 14px;
  border-radius: 999px;
  background: rgb(255 255 255 / 70%);
  border: 1px solid var(--border-subtle);
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  background: transparent;
}

.messages-inner {
  max-width: 820px;
  margin: 0 auto;
  padding: 24px 24px 12px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
}

.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  animation: fadeIn 0.28s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg-row.user {
  justify-content: flex-end;
  gap: 0;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  margin-top: 2px;
  box-shadow: 0 2px 8px rgb(28 25 23 / 12%);
}

.bubble {
  max-width: 100%;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  line-height: 1.65;
}

.msg-row.user .bubble {
  max-width: min(85%, 520px);
  background: var(--brand-gradient);
  color: #fff;
  border: none;
  border-radius: 18px 6px 18px 18px;
  box-shadow: var(--shadow-brand);
  padding: 12px 16px;
}

.msg-row.user .markdown-content {
  color: #fff;
}

.msg-row.assistant .bubble {
  flex: 1;
  min-width: 0;
  background: rgb(255 255 255 / 92%);
  border: 1px solid rgb(231 229 228 / 90%);
  border-radius: 6px 18px 18px 18px;
  box-shadow: 0 2px 16px rgb(28 25 23 / 5%);
}

.msg-meta {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
}

.citations :deep(.el-collapse) {
  border: none;
}

.citations :deep(.el-collapse-item__header) {
  background: var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  height: 36px;
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
}

.source-item {
  background: var(--border-subtle);
  border-left: 3px solid var(--brand-primary);
  padding: 10px 14px;
  margin-bottom: 8px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.source-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.title-text {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-primary);
}

.excerpt {
  font-size: 12px;
  color: var(--text-body);
  margin: 0;
  white-space: pre-wrap;
}

.suggested {
  margin-top: 4px;
}

.suggested-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}

.suggested-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.suggested-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 8px 14px;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  background: rgb(255 255 255 / 80%);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s;
  font-family: inherit;
}

.suggested-chip:hover {
  border-color: var(--brand-primary-light);
  color: var(--brand-primary-dark);
  background: var(--brand-primary-soft);
  box-shadow: 0 2px 8px rgb(249 115 22 / 12%);
  transform: translateY(-1px);
}

.composer {
  padding: 8px 24px 20px;
  background: transparent;
  border-top: none;
  flex-shrink: 0;
}

.composer-inner {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  max-width: 820px;
  margin: 0 auto;
  padding: 10px 14px 10px 16px;
  background: rgb(255 255 255 / 95%);
  border: 1px solid var(--border-default);
  border-radius: 18px;
  box-shadow: 0 8px 32px rgb(28 25 23 / 8%), 0 2px 8px rgb(28 25 23 / 4%);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.composer-inner:focus-within {
  border-color: var(--brand-primary-light);
  box-shadow: var(--shadow-focus), 0 8px 32px rgb(249 115 22 / 10%);
}

.composer-inner :deep(.el-textarea__inner) {
  background: transparent;
  border: none;
  box-shadow: none !important;
  padding: 6px 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--text-primary);
  min-height: 44px !important;
}

.composer-actions {
  flex-shrink: 0;
  padding-bottom: 2px;
}

.composer-actions .el-button--primary {
  padding: 10px 22px;
  font-weight: 600;
}

.form-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.markdown-content {
  font-size: 14px;
  line-height: 1.75;
  word-break: break-word;
  color: var(--text-primary);
}

.markdown-content :deep(p) {
  margin: 0 0 10px;
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin: 16px 0 8px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.markdown-content :deep(h3) {
  font-size: 15px;
  padding-left: 10px;
  border-left: 3px solid var(--brand-primary);
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 8px 0;
  padding-left: 1.4em;
}

.markdown-content :deep(li) {
  margin-bottom: 6px;
}

.markdown-content :deep(li::marker) {
  color: var(--brand-primary);
}

.markdown-content :deep(blockquote) {
  margin: 10px 0;
  padding: 10px 14px;
  border-left: 3px solid var(--brand-primary-light);
  background: var(--brand-primary-soft);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--text-secondary);
}

.markdown-content :deep(pre) {
  background: #292524;
  color: #fafaf9;
  padding: 14px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  font-size: 13px;
  margin: 10px 0;
}

.markdown-content :deep(code) {
  font-size: 0.92em;
  background: var(--border-subtle);
  padding: 2px 6px;
  border-radius: 4px;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
}

.bubble.status {
  background: var(--brand-primary-soft);
  border: 1px solid var(--brand-primary-light);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
}

.thinking-indicator {
  display: flex;
  gap: 4px;
}

.thinking-indicator .dot {
  width: 6px;
  height: 6px;
  background: var(--brand-primary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.thinking-indicator .dot:nth-child(1) { animation-delay: -0.32s; }
.thinking-indicator .dot:nth-child(2) { animation-delay: -0.16s; }

.status-text {
  font-size: 13px;
  color: var(--brand-primary-dark);
  font-weight: 500;
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.streaming .cursor {
  animation: blink 1s infinite;
  color: var(--brand-primary);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.panel-body::-webkit-scrollbar,
.messages::-webkit-scrollbar,
.panel-rail::-webkit-scrollbar {
  width: 5px;
}

.panel-body::-webkit-scrollbar-thumb,
.messages::-webkit-scrollbar-thumb,
.panel-rail::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}
</style>
