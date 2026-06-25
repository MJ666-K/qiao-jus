<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile } from "element-plus";
import {
  Delete,
  Document,
  EditPen,
  FolderOpened,
  MoreFilled,
  Plus,
  Refresh,
  Upload,
} from "@element-plus/icons-vue";
import {
  createDataset,
  deleteDataset,
  listDatasets,
  updateDataset,
} from "@/api/datasets";
import {
  deleteDocument,
  getDocument,
  listDocuments,
  reindexDocument,
  uploadDocument,
} from "@/api/documents";
import { listChunks } from "@/api/chunks";
import { useAuthStore } from "@/stores/auth";
import DocStatusTag from "@/components/DocStatusTag.vue";
import { DOC_TYPES, SYSTEM_DATASET_NAMES, docTypeLabel } from "@/constants/docTypes";
import type {
  Dataset,
  DocumentItem,
  DocumentListSummary,
} from "@/types";

const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const datasets = ref<Dataset[]>([]);
const documents = ref<DocumentItem[]>([]);
const activeTab = ref<"user" | "platform">("user");
const selectedDatasetId = ref("");
const docTypeFilter = ref("");
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const summary = ref<DocumentListSummary>({ done: 0, processing: 0, failed: 0 });
const createDialogVisible = ref(false);
const editDialogVisible = ref(false);
const uploadDialogVisible = ref(false);
const uploadSubmitting = ref(false);
const uploadDocType = ref("contract");
const pendingFiles = ref<File[]>([]);
const uploadFileList = ref<UploadFile[]>([]);

const UPLOAD_FILE_LIMIT = 20;
const ALLOWED_UPLOAD_EXT = [
  ".md",
  ".markdown",
  ".txt",
  ".pdf",
  ".docx",
  ".html",
  ".htm",
] as const;
const UPLOAD_ACCEPT =
  ".md,.markdown,.txt,.pdf,.docx,.html,.htm,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,text/html";
const detailDrawerOpen = ref(false);
const detailLoading = ref(false);
const detailDoc = ref<DocumentItem | null>(null);
const detailContent = ref("");
const detailChunkCount = ref(0);
const editingDataset = ref<Dataset | null>(null);
const libraryForm = ref({ name: "", description: "", doc_type: "contract" });
let pollTimer: ReturnType<typeof setInterval> | null = null;

const PLATFORM_DOC_TYPES = ["law", "case", "compliance"];
const isAdmin = computed(() => auth.user?.role === "admin");

function datasetScope(ds: Dataset): "user" | "platform" {
  return String(ds.metadata?.scope || "user") === "platform"
    ? "platform"
    : "user";
}

const librariesForTab = computed(() =>
  datasets.value.filter((ds) => {
    if (SYSTEM_DATASET_NAMES.has(ds.name) || ds.metadata?.system) return false;
    return activeTab.value === "platform"
      ? datasetScope(ds) === "platform"
      : datasetScope(ds) === "user";
  }),
);

const selectedDataset = computed(
  () =>
    librariesForTab.value.find((ds) => ds.id === selectedDatasetId.value) ??
    null,
);

const canCreateLibrary = computed(() =>
  activeTab.value === "user" ? true : isAdmin.value,
);

const docTypeOptions = computed(() =>
  DOC_TYPES.filter(
    (t) => t.scope === (activeTab.value === "platform" ? "platform" : "user"),
  ),
);

const selectedDocTypeLabel = computed(() => docTypeLabel(uploadDocType.value));

const uploadTypeOptions = computed(() =>
  activeTab.value === "platform"
    ? DOC_TYPES.filter((t) => t.scope === "platform")
    : DOC_TYPES.filter((t) => t.scope === "user"),
);

function isPlatformDoc(row: DocumentItem): boolean {
  const ds = datasets.value.find((d) => d.id === row.dataset_id);
  if (ds) return datasetScope(ds) === "platform";
  return PLATFORM_DOC_TYPES.includes(String(row.metadata?.doc_type || ""));
}

async function loadDatasets() {
  datasets.value = await listDatasets();
  ensureSelectedLibrary();
}

function ensureSelectedLibrary() {
  const libs = librariesForTab.value;
  if (!libs.length) {
    selectedDatasetId.value = "";
    return;
  }
  if (!libs.some((d) => d.id === selectedDatasetId.value)) {
    selectedDatasetId.value = libs[0].id;
  }
}

async function loadDocuments() {
  if (!selectedDatasetId.value) {
    documents.value = [];
    total.value = 0;
    summary.value = { done: 0, processing: 0, failed: 0 };
    return;
  }
  loading.value = true;
  try {
    const res = await listDocuments({
      dataset_id: selectedDatasetId.value,
      doc_type: docTypeFilter.value || undefined,
      uploaded_only: true,
      page: page.value,
      page_size: pageSize.value,
    });
    documents.value = res.items;
    total.value = res.total;
    summary.value = res.summary;
  } finally {
    loading.value = false;
  }
}

async function refreshAll() {
  await loadDatasets();
  await loadDocuments();
}

function openCreateLibrary() {
  libraryForm.value = {
    name: "",
    description: "",
    doc_type: docTypeOptions.value[0]?.id ?? "contract",
  };
  createDialogVisible.value = true;
}

async function submitCreateLibrary() {
  if (!libraryForm.value.name.trim()) {
    ElMessage.warning("请输入知识库名称");
    return;
  }
  try {
    const scope = activeTab.value === "platform" ? "platform" : "user";
    const ds = await createDataset({
      name: libraryForm.value.name.trim(),
      description: libraryForm.value.description.trim() || null,
      metadata: { scope, doc_type: libraryForm.value.doc_type },
    });
    createDialogVisible.value = false;
    ElMessage.success("知识库已创建");
    await loadDatasets();
    selectedDatasetId.value = ds.id;
    page.value = 1;
    await loadDocuments();
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "创建失败");
  }
}

function openEditLibrary(ds: Dataset) {
  editingDataset.value = ds;
  libraryForm.value = {
    name: ds.name,
    description: ds.description || "",
    doc_type: String(ds.metadata?.doc_type || "contract"),
  };
  editDialogVisible.value = true;
}

async function submitEditLibrary() {
  if (!editingDataset.value || !libraryForm.value.name.trim()) return;
  try {
    await updateDataset(editingDataset.value.id, {
      name: libraryForm.value.name.trim(),
      description: libraryForm.value.description.trim() || null,
    });
    editDialogVisible.value = false;
    ElMessage.success("已更新");
    await loadDatasets();
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "更新失败");
  }
}

async function removeLibrary(ds: Dataset) {
  const count = ds.document_count ?? 0;
  const msg =
    count > 0
      ? `知识库「${ds.name}」内有 ${count} 篇文档，删除后将一并清除，确认？`
      : `确定删除知识库「${ds.name}」？`;
  try {
    await ElMessageBox.confirm(msg, "删除知识库", { type: "warning" });
    await deleteDataset(ds.id);
    ElMessage.success("已删除");
    if (selectedDatasetId.value === ds.id) selectedDatasetId.value = "";
    page.value = 1;
    await refreshAll();
  } catch (e) {
    if (e === "cancel") return;
    ElMessage.error(e instanceof Error ? e.message : "删除失败");
  }
}

function isAllowedUploadName(name: string): boolean {
  const lower = name.toLowerCase();
  return ALLOWED_UPLOAD_EXT.some((ext) => lower.endsWith(ext));
}

function openUploadDialog() {
  if (!selectedDatasetId.value) {
    ElMessage.warning("请先选择知识库");
    return;
  }
  pendingFiles.value = [];
  uploadFileList.value = [];
  uploadDocType.value = String(
    selectedDataset.value?.metadata?.doc_type ||
      uploadTypeOptions.value[0]?.id ||
      "general",
  );
  uploadDialogVisible.value = true;
}

function onUploadFilesChange(_file: UploadFile, fileList: UploadFile[]) {
  const valid: UploadFile[] = [];
  const files: File[] = [];
  for (const item of fileList) {
    if (!item.raw) continue;
    if (!isAllowedUploadName(item.name)) {
      ElMessage.warning(`不支持的文件格式：${item.name}（支持 PDF、DOCX、MD、TXT、HTML）`);
      continue;
    }
    valid.push(item);
    files.push(item.raw);
  }
  uploadFileList.value = valid;
  pendingFiles.value = files;
}

function onUploadExceed() {
  ElMessage.warning(`最多同时选择 ${UPLOAD_FILE_LIMIT} 个文件`);
}

function removePendingFile(index: number) {
  pendingFiles.value = pendingFiles.value.filter((_, i) => i !== index);
  uploadFileList.value = uploadFileList.value.filter((_, i) => i !== index);
}

function clearPendingFiles() {
  pendingFiles.value = [];
  uploadFileList.value = [];
}

function onUploadFileRemove() {
  clearPendingFiles();
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function confirmUpload() {
  if (!pendingFiles.value.length || !selectedDatasetId.value) {
    ElMessage.warning("请先选择文件");
    return;
  }
  uploadSubmitting.value = true;
  let success = 0;
  const failed: string[] = [];
  try {
    for (const file of pendingFiles.value) {
      try {
        await uploadDocument(
          file,
          selectedDatasetId.value,
          uploadDocType.value,
        );
        success += 1;
      } catch (e) {
        failed.push(
          `${file.name}：${e instanceof Error ? e.message : "上传失败"}`,
        );
      }
    }
    if (success === pendingFiles.value.length) {
      ElMessage.success(`已成功上传 ${success} 个文件`);
      uploadDialogVisible.value = false;
      clearPendingFiles();
      page.value = 1;
      await refreshAll();
    } else if (success > 0) {
      ElMessage.warning(
        `成功 ${success} 个，失败 ${failed.length} 个。${failed[0] ?? ""}`,
      );
      uploadDialogVisible.value = false;
      clearPendingFiles();
      page.value = 1;
      await refreshAll();
    } else {
      ElMessage.error(failed[0] ?? "全部上传失败");
    }
  } finally {
    uploadSubmitting.value = false;
  }
}

async function openDetail(id: string) {
  detailDrawerOpen.value = true;
  detailLoading.value = true;
  detailDoc.value = null;
  detailContent.value = "";
  detailChunkCount.value = 0;
  try {
    const [doc, chunks] = await Promise.all([
      getDocument(id),
      listChunks(id).catch(() => []),
    ]);
    detailDoc.value = doc;
    detailChunkCount.value = chunks.length;
    detailContent.value = chunks
      .sort((a, b) => a.chunk_index - b.chunk_index)
      .map((c) => c.text)
      .join("\n\n");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "加载失败");
    detailDrawerOpen.value = false;
  } finally {
    detailLoading.value = false;
  }
}

async function reindex(id: string) {
  await ElMessageBox.confirm(
    "将清空并重建该文档的 chunks/向量/图谱，确认？",
    "重新索引",
    {
      type: "warning",
    },
  );
  const r = await reindexDocument(id);
  ElMessage.success(r.message || "已触发重新索引");
  await loadDocuments();
}

async function remove(id: string) {
  await ElMessageBox.confirm(
    "删除文档及其所有 chunks/向量/图谱，确认？",
    "删除",
    {
      type: "warning",
    },
  );
  await deleteDocument(id);
  ElMessage.success("已删除");
  if (documents.value.length === 1 && page.value > 1) page.value -= 1;
  await refreshAll();
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fileExt(title: string): string {
  const m = title.match(/\.([^.]+)$/i);
  if (!m) return "FILE";
  const ext = m[1].toUpperCase();
  return ext.length > 4 ? ext.slice(0, 4) : ext;
}

function fileExtClass(title: string): string {
  const ext = (title.split(".").pop() || "").toLowerCase();
  if (ext === "pdf") return "ext-pdf";
  if (ext === "docx" || ext === "doc") return "ext-doc";
  if (ext === "md") return "ext-md";
  if (ext === "html" || ext === "htm") return "ext-html";
  if (ext === "txt") return "ext-txt";
  return "ext-default";
}

function rowStatusClass(status: string): string {
  if (status === "done") return "row-done";
  if (status === "failed") return "row-failed";
  return "row-processing";
}

function libraryInitial(name: string) {
  return name.trim().charAt(0) || "库";
}

function canManageLibrary(ds: Dataset) {
  if (datasetScope(ds) === "user") return true;
  return isAdmin.value;
}

async function handleDocAction(cmd: string, doc: DocumentItem) {
  if (cmd === "reindex") await reindex(doc.id);
  else if (cmd === "delete") await remove(doc.id);
}

function goToChunks(id: string) {
  detailDrawerOpen.value = false;
  router.push(`/documents/${id}/chunks`);
}

function onPageChange(p: number) {
  page.value = p;
  loadDocuments();
}

function onPageSizeChange(size: number) {
  pageSize.value = size;
  page.value = 1;
  loadDocuments();
}

watch(activeTab, () => {
  docTypeFilter.value = "";
  page.value = 1;
  ensureSelectedLibrary();
  loadDocuments();
});

watch(selectedDatasetId, () => {
  page.value = 1;
  loadDocuments();
});

watch(docTypeFilter, () => {
  page.value = 1;
  loadDocuments();
});

onMounted(async () => {
  await refreshAll();
  pollTimer = setInterval(() => {
    if (selectedDatasetId.value) loadDocuments();
  }, 8000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <div class="documents-page">
    <header class="page-header card-panel">
      <div class="tab-switch">
        <button
          type="button"
          class="tab-btn"
          :class="{ active: activeTab === 'user' }"
          @click="activeTab = 'user'"
        >
          <el-icon><Document /></el-icon>
          私有知识库
        </button>
        <button
          type="button"
          class="tab-btn"
          :class="{ active: activeTab === 'platform' }"
          @click="activeTab = 'platform'"
        >
          <el-icon><FolderOpened /></el-icon>
          平台公共库
        </button>
      </div>
      <div v-if="selectedDataset" class="header-stats">
        <span
          ><strong>{{ total }}</strong> 文档</span
        >
        <span
          ><strong>{{ summary.done }}</strong> 已完成</span
        >
        <span v-if="summary.processing"
          ><strong>{{ summary.processing }}</strong> 处理中</span
        >
      </div>
    </header>

    <div class="workspace">
      <aside class="library-sidebar card-panel">
        <div class="sidebar-head">
          <h3>{{ activeTab === "user" ? "私有库列表" : "公共库列表" }}</h3>
          <span class="count">{{ librariesForTab.length }}</span>
        </div>

        <button
          v-if="canCreateLibrary"
          type="button"
          class="create-lib-btn"
          @click="openCreateLibrary"
        >
          <el-icon><Plus /></el-icon>
          新建知识库
        </button>

        <div v-loading="loading" class="library-list">
          <el-empty
            v-if="!librariesForTab.length"
            :image-size="56"
            :description="
              activeTab === 'user' ? '暂无私有库，请先创建' : '暂无公共库'
            "
          >
            <el-button
              v-if="canCreateLibrary"
              type="primary"
              size="small"
              @click="openCreateLibrary"
            >
              创建第一个库
            </el-button>
          </el-empty>

          <button
            v-for="ds in librariesForTab"
            :key="ds.id"
            type="button"
            class="library-item"
            :class="{ active: selectedDatasetId === ds.id }"
            @click="selectedDatasetId = ds.id"
          >
            <div class="lib-avatar">{{ libraryInitial(ds.name) }}</div>
            <div class="lib-info">
              <div class="lib-name">{{ ds.name }}</div>
              <div class="lib-meta">
                <span>{{
                  docTypeLabel(String(ds.metadata?.doc_type || ""))
                }}</span>
                <span class="dot">·</span>
                <span>{{ ds.document_count ?? 0 }} 篇</span>
              </div>
            </div>
            <el-dropdown
              v-if="canManageLibrary(ds)"
              trigger="click"
              @click.stop
              @command="
                (cmd: string) =>
                  cmd === 'edit' ? openEditLibrary(ds) : removeLibrary(ds)
              "
            >
              <el-icon class="lib-more" @click.stop><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">
                    <el-icon><EditPen /></el-icon>重命名
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" divided>
                    <el-icon><Delete /></el-icon>删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </button>
        </div>
      </aside>

      <main class="doc-main card-panel">
        <template v-if="selectedDataset">
          <div class="main-toolbar">
            <div class="toolbar-left">
              <h2 class="lib-title">{{ selectedDataset.name }}</h2>
              <p v-if="selectedDataset.description" class="lib-desc">
                {{ selectedDataset.description }}
              </p>
            </div>
            <div class="toolbar-right">
              <el-select
                v-model="docTypeFilter"
                placeholder="文档类型"
                clearable
                class="type-filter"
              >
                <el-option
                  v-for="t in docTypeOptions"
                  :key="t.id"
                  :label="t.label"
                  :value="t.id"
                />
              </el-select>
              <el-button
                :icon="Refresh"
                :loading="loading"
                @click="loadDocuments"
                >刷新</el-button
              >
              <el-button
                v-if="activeTab === 'user'"
                type="primary"
                :icon="Upload"
                @click="openUploadDialog"
              >
                上传文档
              </el-button>
            </div>
          </div>

          <p v-if="activeTab === 'user'" class="upload-hint">
            支持批量上传 PDF、DOCX、MD、TXT、HTML
          </p>
          <p v-else class="upload-hint muted">
            平台公共库只读，如需扩充请联系管理员
          </p>

          <div v-loading="loading" class="doc-list-wrap">
            <el-empty
              v-if="!documents.length"
              :image-size="72"
              :description="
                activeTab === 'user' ? '该库暂无文档' : '该库暂无文档'
              "
            >
              <el-button
                v-if="activeTab === 'user'"
                type="primary"
                :icon="Upload"
                @click="openUploadDialog"
              >
                上传第一份文档
              </el-button>
            </el-empty>

            <template v-else>
              <div class="doc-table-panel">
                <div class="doc-table-head">
                  <span class="col-name">文档名称</span>
                  <span class="col-type">类型</span>
                  <span class="col-status">状态</span>
                  <span class="col-time">上传时间</span>
                  <span class="col-actions">操作</span>
                </div>

                <ul class="doc-list">
                  <li
                    v-for="doc in documents"
                    :key="doc.id"
                    class="doc-row"
                    :class="rowStatusClass(doc.status)"
                  >
                    <div class="col-name">
                      <div class="file-badge" :class="fileExtClass(doc.title)">
                        {{ fileExt(doc.title) }}
                      </div>
                      <div class="name-block">
                        <span class="doc-title" :title="doc.title">{{
                          doc.title
                        }}</span>
                      </div>
                    </div>

                    <div class="col-type">
                      <span class="type-chip">
                        {{ docTypeLabel(String(doc.metadata?.doc_type || "")) }}
                      </span>
                    </div>

                    <div class="col-status">
                      <DocStatusTag :status="doc.status" />
                    </div>

                    <div class="col-time">
                      <span class="time-main">{{
                        formatTime(doc.created_at)
                      }}</span>
                    </div>

                    <div class="col-actions">
                      <div class="action-group">
                        <button
                          type="button"
                          class="act-btn act-primary"
                          @click.stop="openDetail(doc.id)"
                        >
                          详情
                        </button>
                        <button
                          type="button"
                          class="act-btn"
                          @click.stop="
                            router.push(`/documents/${doc.id}/chunks`)
                          "
                        >
                          文本块
                        </button>
                        <el-dropdown
                          v-if="!isPlatformDoc(doc)"
                          trigger="click"
                          @command="(cmd: string) => handleDocAction(cmd, doc)"
                        >
                          <button
                            type="button"
                            class="act-btn act-more"
                            @click.stop
                          >
                            <el-icon><MoreFilled /></el-icon>
                          </button>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item command="reindex"
                                >重新索引</el-dropdown-item
                              >
                              <el-dropdown-item command="delete" divided
                                >删除</el-dropdown-item
                              >
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                      </div>
                    </div>
                  </li>
                </ul>
              </div>

              <div class="pagination-bar">
                <el-pagination
                  v-model:current-page="page"
                  v-model:page-size="pageSize"
                  :total="total"
                  :page-sizes="[10, 20, 50]"
                  layout="total, sizes, prev, pager, next"
                  background
                  @current-change="onPageChange"
                  @size-change="onPageSizeChange"
                />
              </div>
            </template>
          </div>
        </template>

        <el-empty
          v-else
          :image-size="80"
          description="请从左侧选择或创建知识库"
        >
          <el-button
            v-if="canCreateLibrary"
            type="primary"
            :icon="Plus"
            @click="openCreateLibrary"
          >
            新建知识库
          </el-button>
        </el-empty>
      </main>
    </div>

    <!-- 上传确认弹窗 -->
    <el-dialog
      v-model="uploadDialogVisible"
      width="520px"
      destroy-on-close
      class="upload-dialog"
      :show-close="true"
    >
      <template #header>
        <div class="upload-dialog-head">
          <div class="upload-dialog-icon">
            <el-icon><Upload /></el-icon>
          </div>
          <div>
            <h3 class="upload-dialog-title">批量上传文档</h3>
            <p class="upload-dialog-sub">可同时选择多个文件，确认后依次上传</p>
          </div>
        </div>
      </template>

      <div class="upload-dialog-body">
        <div class="upload-info-grid">
          <div class="upload-info-item">
            <span class="upload-info-label">目标知识库</span>
            <span class="upload-info-value">{{
              selectedDataset?.name ?? "—"
            }}</span>
          </div>
          <div class="upload-info-item">
            <span class="upload-info-label">文档类型</span>
            <el-select v-model="uploadDocType" class="upload-type-select">
              <el-option
                v-for="t in uploadTypeOptions"
                :key="t.id"
                :label="t.label"
                :value="t.id"
              />
            </el-select>
          </div>
        </div>

        <div class="upload-file-zone">
          <el-upload
            class="upload-picker"
            v-model:file-list="uploadFileList"
            :auto-upload="false"
            multiple
            :limit="UPLOAD_FILE_LIMIT"
            :show-file-list="false"
            :accept="UPLOAD_ACCEPT"
            :on-change="onUploadFilesChange"
            :on-remove="onUploadFileRemove"
            :on-exceed="onUploadExceed"
          >
            <div class="upload-placeholder">
              <el-icon class="upload-placeholder-icon"><Upload /></el-icon>
              <p class="upload-placeholder-title">点击选择文件（可多选）</p>
              <p class="upload-placeholder-tip">
                支持 PDF · DOCX · MD · TXT · HTML，单次最多 {{ UPLOAD_FILE_LIMIT }} 个
              </p>
            </div>
          </el-upload>

          <ul v-if="pendingFiles.length" class="batch-file-list">
            <li
              v-for="(file, index) in pendingFiles"
              :key="`${file.name}-${file.size}-${index}`"
              class="file-preview-card"
            >
              <div
                class="file-preview-badge"
                :class="fileExtClass(file.name)"
              >
                {{ fileExt(file.name) }}
              </div>
              <div class="file-preview-info">
                <div class="file-name">{{ file.name }}</div>
                <div class="file-meta">
                  {{ formatFileSize(file.size) }} · {{ selectedDocTypeLabel }}
                </div>
              </div>
              <el-button link type="danger" @click="removePendingFile(index)">
                移除
              </el-button>
            </li>
          </ul>
        </div>

        <div class="upload-pipeline">
          <span>上传</span><span class="pipe-arrow">→</span> <span>解析</span
          ><span class="pipe-arrow">→</span> <span>切块</span
          ><span class="pipe-arrow">→</span> <span>向量化</span
          ><span class="pipe-arrow">→</span>
          <span>建图</span>
        </div>
      </div>

      <template #footer>
        <div class="upload-dialog-footer">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="uploadSubmitting"
            :disabled="!pendingFiles.length"
            @click="confirmUpload"
          >
            确认上传{{ pendingFiles.length ? `（${pendingFiles.length}）` : "" }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 文档详情抽屉 -->
    <el-drawer
      v-model="detailDrawerOpen"
      direction="rtl"
      size="560px"
      destroy-on-close
      class="detail-drawer"
    >
      <template #header>
        <div class="detail-drawer-head">
          <div
            v-if="detailDoc"
            class="detail-file-badge"
            :class="fileExtClass(detailDoc.title)"
          >
            {{ fileExt(detailDoc.title) }}
          </div>
          <div class="detail-drawer-titles">
            <h3 class="detail-title">{{ detailDoc?.title ?? "文档详情" }}</h3>
            <div v-if="detailDoc" class="detail-tags">
              <DocStatusTag :status="detailDoc.status" />
              <span class="detail-type-chip">{{
                docTypeLabel(String(detailDoc.metadata?.doc_type || ""))
              }}</span>
            </div>
          </div>
        </div>
      </template>

      <div v-loading="detailLoading" class="detail-panel">
        <template v-if="detailDoc">
          <section class="detail-content-section">
            <div class="detail-section-head">
              <h4>文档内容</h4>
              <span v-if="detailChunkCount" class="detail-content-meta"
                >共 {{ detailChunkCount }} 个文本块</span
              >
            </div>

            <div v-if="detailContent" class="detail-content-box">
              <pre class="detail-content-text">{{ detailContent }}</pre>
            </div>
            <div v-else-if="detailDoc.status === 'failed'" class="detail-empty detail-empty-error">
              <p>文档处理失败，暂无内容</p>
              <pre v-if="detailDoc.error" class="error-text">{{ detailDoc.error }}</pre>
            </div>
            <div v-else-if="detailDoc.status !== 'done'" class="detail-empty">
              <p>文档处理中，内容将在切块完成后显示</p>
            </div>
            <div v-else class="detail-empty">
              <p>暂无文本内容</p>
            </div>
          </section>

          <el-collapse class="detail-collapse">
            <el-collapse-item title="基本信息" name="meta">
              <dl class="detail-dl">
                <dt>所属范围</dt>
                <dd>{{ detailDoc.scope === "user" ? "私有" : "公共" }}</dd>
                <dt>上传时间</dt>
                <dd>{{ formatTime(detailDoc.created_at) }}</dd>
                <dt v-if="detailDoc.updated_at">更新时间</dt>
                <dd v-if="detailDoc.updated_at">{{ formatTime(detailDoc.updated_at) }}</dd>
                <dt v-if="detailDoc.mime_type">文件格式</dt>
                <dd v-if="detailDoc.mime_type">{{ detailDoc.mime_type }}</dd>
                <dt>文档 ID</dt>
                <dd><code class="detail-id-inline">{{ detailDoc.id }}</code></dd>
              </dl>
            </el-collapse-item>
          </el-collapse>

          <div class="detail-actions">
            <el-button type="primary" @click="goToChunks(detailDoc.id)">文本块管理</el-button>
            <template v-if="!isPlatformDoc(detailDoc)">
              <el-button @click="reindex(detailDoc.id)">重新索引</el-button>
              <el-button type="danger" plain @click="remove(detailDoc.id)">删除</el-button>
            </template>
          </div>
        </template>
      </div>
    </el-drawer>

    <!-- 新建知识库 -->
    <el-dialog
      v-model="createDialogVisible"
      :title="activeTab === 'user' ? '新建私有知识库' : '新建平台公共库'"
      width="440px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input
            v-model="libraryForm.name"
            :placeholder="
              activeTab === 'user' ? '如：劳动合同库' : '如：劳动法规库'
            "
          />
        </el-form-item>
        <el-form-item label="默认文档类型" required>
          <el-select v-model="libraryForm.doc_type" style="width: 100%">
            <el-option
              v-for="t in docTypeOptions"
              :key="t.id"
              :label="t.label"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="libraryForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreateLibrary">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑知识库 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑知识库"
      width="440px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="libraryForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="libraryForm.description"
            type="textarea"
            :rows="3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEditLibrary">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.documents-page {
  display: flex;
  flex-direction: column;
  gap: var(--gap-section);
  min-width: 0;
  height: calc(100vh - var(--topbar-height) - var(--page-padding-y) * 2);
  min-height: 520px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #fffbf5 0%, var(--brand-surface) 100%);
  border-color: rgb(249 115 22 / 10%);
}

.tab-switch {
  display: inline-flex;
  gap: 6px;
  padding: 4px;
  background: rgb(28 25 23 / 4%);
  border-radius: var(--radius-md);
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s,
    box-shadow 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: rgb(255 255 255 / 60%);
}

.tab-btn.active {
  background: var(--brand-surface);
  color: var(--brand-primary-dark);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.header-stats {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: var(--text-muted);
}

.header-stats strong {
  color: var(--brand-primary-dark);
  font-weight: 700;
  margin-right: 2px;
}

.workspace {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: var(--gap-section);
  flex: 1;
  min-height: 0;
}

.library-sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 16px;
  background: linear-gradient(180deg, #fafaf9 0%, var(--brand-surface) 100%);
}

.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.sidebar-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-head .count {
  font-size: 12px;
  color: var(--text-muted);
  background: rgb(28 25 23 / 5%);
  padding: 2px 8px;
  border-radius: 10px;
}

.create-lib-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  margin-bottom: 12px;
  padding: 9px 12px;
  border: 1px dashed var(--brand-primary);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--brand-primary-dark);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.create-lib-btn:hover {
  background: var(--brand-primary-soft);
  border-color: var(--brand-primary-dark);
}

.library-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}

.library-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.library-item:hover {
  background: rgb(255 255 255 / 70%);
}

.library-item.active {
  background: var(--brand-primary-soft);
  border-color: rgb(249 115 22 / 25%);
}

.lib-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--brand-primary-soft), #ffedd5);
  color: var(--brand-primary-dark);
  font-weight: 700;
  font-size: 14px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.library-item.active .lib-avatar {
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-primary-dark)
  );
  color: #fff;
}

.lib-info {
  flex: 1;
  min-width: 0;
}

.lib-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lib-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.lib-meta .dot {
  margin: 0 3px;
}

.lib-more {
  flex-shrink: 0;
  color: var(--text-muted);
  padding: 4px;
  border-radius: 4px;
}

.lib-more:hover {
  color: var(--brand-primary);
  background: rgb(249 115 22 / 10%);
}

.doc-main {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  padding: 18px 20px;
}

.main-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.lib-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.lib-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.type-filter {
  width: 150px;
}

.upload-hint {
  margin: 0 0 14px;
  font-size: 12px;
  color: var(--text-muted);
}

.upload-hint.muted {
  color: var(--text-secondary);
}

.doc-list-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.doc-table-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: #fafaf9;
  overflow: hidden;
}

.doc-table-head,
.doc-row {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) 108px 96px 148px minmax(180px, auto);
  align-items: center;
  gap: 12px;
  padding: 0 16px;
}

.doc-table-head {
  height: 40px;
  background: linear-gradient(180deg, #fff 0%, #fafaf9 100%);
  border-bottom: 1px solid var(--border-default);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.doc-list {
  list-style: none;
  margin: 0;
  padding: 6px 0;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.doc-row {
  position: relative;
  min-height: 68px;
  margin: 4px 8px;
  padding: 12px 16px 12px 20px;
  border-radius: var(--radius-sm);
  background: var(--brand-surface);
  border: 1px solid transparent;
  transition:
    border-color 0.15s,
    box-shadow 0.15s,
    transform 0.12s;
}

.doc-row::before {
  content: "";
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: #d6d3d1;
}

.doc-row.row-done::before {
  background: #10b981;
}

.doc-row.row-failed::before {
  background: #ef4444;
}

.doc-row.row-processing::before {
  background: #f59e0b;
}

.doc-row:hover {
  border-color: rgb(249 115 22 / 18%);
  box-shadow: 0 2px 12px rgb(249 115 22 / 8%);
  transform: translateY(-1px);
}

.col-name {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.file-badge {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.02em;
  flex-shrink: 0;
  border: 1px solid transparent;
}

.file-badge.ext-pdf {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}

.file-badge.ext-doc {
  background: #eff6ff;
  color: #2563eb;
  border-color: #bfdbfe;
}

.file-badge.ext-md {
  background: #ecfdf5;
  color: #059669;
  border-color: #a7f3d0;
}

.file-badge.ext-html {
  background: #fff7ed;
  color: #ea580c;
  border-color: #fed7aa;
}

.file-badge.ext-txt {
  background: #f5f5f4;
  color: #57534e;
  border-color: #e7e5e4;
}

.file-badge.ext-default {
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
  border-color: rgb(249 115 22 / 20%);
}

.name-block {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.doc-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.type-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: #f5f5f4;
  border: 1px solid var(--border-subtle);
  white-space: nowrap;
}

.col-time {
  font-size: 12px;
  color: var(--text-muted);
}

.time-main {
  white-space: nowrap;
}

.col-actions {
  display: flex;
  justify-content: flex-end;
}

.action-group {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  background: #f5f5f4;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
}

.act-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 5px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s,
    box-shadow 0.15s;
  white-space: nowrap;
}

.act-btn:hover {
  background: #fff;
  color: var(--brand-primary-dark);
}

.act-btn.act-primary {
  background: #fff;
  color: var(--brand-primary-dark);
  box-shadow: 0 1px 2px rgb(28 25 23 / 6%);
}

.act-btn.act-more {
  padding: 5px 8px;
  min-width: 28px;
}

.act-btn.act-more .el-icon {
  font-size: 14px;
}

.pagination-bar {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
  margin-top: 8px;
  border-top: 1px solid var(--border-subtle);
}

.upload-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* 上传弹窗 */
.upload-dialog-head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.upload-dialog-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-primary-dark)
  );
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 22px;
  flex-shrink: 0;
}

.upload-dialog-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.upload-dialog-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.upload-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.upload-info-item {
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: #fafaf9;
  border: 1px solid var(--border-subtle);
}

.upload-info-label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.upload-info-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.upload-type-select {
  width: 100%;
}

.upload-file-zone {
  border: 1px dashed rgb(249 115 22 / 30%);
  border-radius: var(--radius-md);
  background: linear-gradient(180deg, #fffbf5 0%, #fff 100%);
  overflow: hidden;
}

.upload-picker {
  width: 100%;
}

.upload-picker :deep(.el-upload) {
  width: 100%;
  display: block;
}

.upload-placeholder {
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s;
}

.upload-placeholder:hover {
  background: rgb(249 115 22 / 4%);
}

.upload-placeholder-icon {
  font-size: 32px;
  color: var(--brand-primary);
  margin-bottom: 8px;
}

.upload-placeholder-title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.upload-placeholder-tip {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.file-preview-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}

.batch-file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 240px;
  overflow-y: auto;
  border-top: 1px solid var(--border-subtle);
}

.batch-file-list .file-preview-card {
  border-bottom: 1px solid var(--border-subtle);
}

.batch-file-list .file-preview-card:last-child {
  border-bottom: none;
}

.file-preview-badge {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 800;
  flex-shrink: 0;
}

.file-preview-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  word-break: break-all;
}

.file-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.upload-pipeline {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  padding: 10px;
  background: #fafaf9;
  border-radius: var(--radius-sm);
}

.pipe-arrow {
  color: var(--brand-primary-light);
  font-weight: 600;
}

.upload-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* 详情抽屉 */
.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 200px;
  height: 100%;
}

.detail-drawer-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding-right: 24px;
}

.detail-drawer-titles {
  flex: 1;
  min-width: 0;
}

.detail-file-badge {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 800;
  flex-shrink: 0;
  border: 1px solid transparent;
}

.detail-file-badge.ext-pdf { background: #fef2f2; color: #dc2626; border-color: #fecaca; }
.detail-file-badge.ext-doc { background: #eff6ff; color: #2563eb; border-color: #bfdbfe; }
.detail-file-badge.ext-md { background: #ecfdf5; color: #059669; border-color: #a7f3d0; }
.detail-file-badge.ext-html { background: #fff7ed; color: #ea580c; border-color: #fed7aa; }
.detail-file-badge.ext-txt { background: #f5f5f4; color: #57534e; border-color: #e7e5e4; }
.detail-file-badge.ext-default { background: var(--brand-primary-soft); color: var(--brand-primary-dark); border-color: rgb(249 115 22 / 20%); }

.detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  word-break: break-all;
  line-height: 1.4;
}

.detail-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.detail-type-chip {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: #f5f5f4;
  border: 1px solid var(--border-subtle);
}

.detail-content-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.detail-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.detail-section-head h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-content-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.detail-content-box {
  flex: 1;
  min-height: 200px;
  max-height: calc(100vh - 280px);
  overflow: hidden;
  border: 1px solid rgb(249 115 22 / 15%);
  border-radius: var(--radius-md);
  background: linear-gradient(180deg, #fffbf5 0%, #fff 100%);
}

.detail-content-text {
  margin: 0;
  padding: 16px 18px;
  height: 100%;
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.detail-empty {
  padding: 32px 20px;
  text-align: center;
  border-radius: var(--radius-md);
  background: #fafaf9;
  border: 1px dashed var(--border-default);
  color: var(--text-muted);
  font-size: 14px;
}

.detail-empty p {
  margin: 0;
}

.detail-empty-error {
  background: #fef2f2;
  border-color: #fecaca;
  color: #b91c1c;
}

.detail-collapse {
  border: none;
  --el-collapse-header-height: 44px;
}

.detail-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  background: #fafaf9;
  border-radius: var(--radius-sm);
  padding: 0 12px;
  border: 1px solid var(--border-subtle);
}

.detail-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.detail-collapse :deep(.el-collapse-item__content) {
  padding: 12px 4px 0;
}

.detail-dl {
  margin: 0;
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 8px 12px;
  font-size: 13px;
}

.detail-dl dt {
  color: var(--text-muted);
  font-weight: 500;
}

.detail-dl dd {
  margin: 0;
  color: var(--text-primary);
  word-break: break-all;
}

.detail-id-inline {
  font-size: 11px;
  color: var(--text-muted);
  background: #f5f5f4;
  padding: 2px 6px;
  border-radius: 4px;
}

.error-text {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: rgb(255 255 255 / 70%);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  text-align: left;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.detail-drawer :deep(.el-drawer__body) {
  display: flex;
  flex-direction: column;
  padding-top: 8px;
}

@media (max-width: 900px) {
  .documents-page {
    height: auto;
    min-height: 0;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .library-sidebar {
    max-height: 240px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .doc-table-head {
    display: none;
  }

  .doc-row {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 14px 14px 14px 18px;
  }

  .col-type,
  .col-status,
  .col-time {
    padding-left: 52px;
  }

  .col-actions {
    padding-left: 52px;
    justify-content: flex-start;
  }

  .action-group {
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .upload-info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
