<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile } from "element-plus";
import {
  Folder,
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
import {
  DOC_TYPES,
  SYSTEM_DATASET_NAMES,
  docTypeLabel,
} from "@/constants/docTypes";
import type { Dataset, DocumentItem, DocumentListSummary } from "@/types";

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

const TERMINAL_DOC_STATUS = new Set(["done", "failed"]);

const needsDocumentPoll = computed(
  () =>
    summary.value.processing > 0 ||
    documents.value.some((d) => !TERMINAL_DOC_STATUS.has(d.status)),
);

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

/** 私有库所有用户可上传；平台公共库仅管理员 */
const canUploadDocuments = computed(
  () =>
    activeTab.value === "user" ||
    (activeTab.value === "platform" && isAdmin.value),
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

async function loadDocuments(opts: { silent?: boolean } = {}) {
  if (!selectedDatasetId.value) {
    documents.value = [];
    total.value = 0;
    summary.value = { done: 0, processing: 0, failed: 0 };
    return;
  }
  const silent = opts.silent ?? false;
  if (!silent) loading.value = true;
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
    if (silent) {
      await refreshDetailIfOpen();
    }
  } finally {
    if (!silent) loading.value = false;
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
      ElMessage.warning(
        `不支持的文件格式：${item.name}（支持 PDF、DOCX、MD、TXT、HTML）`,
      );
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

async function refreshDetailIfOpen() {
  if (!detailDrawerOpen.value || !detailDoc.value) return;
  const id = detailDoc.value.id;
  if (TERMINAL_DOC_STATUS.has(detailDoc.value.status)) return;
  try {
    const doc = await getDocument(id);
    detailDoc.value = doc;
    if (doc.status === "done") {
      const chunks = await listChunks(id).catch(() => []);
      detailChunkCount.value = chunks.length;
      detailContent.value = chunks
        .sort((a, b) => a.chunk_index - b.chunk_index)
        .map((c) => c.text)
        .join("\n\n");
    }
  } catch {
    /* 静默轮询失败不打断用户 */
  }
}

async function pollDocuments() {
  if (!selectedDatasetId.value || !needsDocumentPoll.value) return;
  await loadDocuments({ silent: true });
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

function formatShortDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const sameYear = d.getFullYear() === now.getFullYear();
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    ...(sameYear ? {} : { year: "numeric" }),
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

function canManageLibrary(ds: Dataset) {
  if (datasetScope(ds) === "user") return true;
  return isAdmin.value;
}

function canManageDoc(doc: DocumentItem): boolean {
  if (!isPlatformDoc(doc)) return true;
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
  pollTimer = setInterval(pollDocuments, 8000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <div class="documents-page">
    <div class="docs-shell card-panel">
      <!-- 顶栏 -->
      <header class="shell-header">
        <div class="header-start">
          <h1 class="shell-title">我的文档</h1>
          <div class="scope-tabs">
            <button
              type="button"
              class="scope-tab"
              :class="{ active: activeTab === 'user' }"
              @click="activeTab = 'user'"
            >
              私有库
            </button>
            <button
              type="button"
              class="scope-tab"
              :class="{ active: activeTab === 'platform' }"
              @click="activeTab = 'platform'"
            >
              公共库
            </button>
          </div>
        </div>
        <div v-if="selectedDataset" class="header-stats">
          <span>{{ total }} 篇</span>
          <span class="dot">·</span>
          <span class="ok">{{ summary.done }} 已完成</span>
          <template v-if="summary.processing">
            <span class="dot">·</span>
            <span class="pending">{{ summary.processing }} 处理中</span>
          </template>
        </div>
      </header>

      <div class="shell-body">
        <!-- 左侧知识库 -->
        <aside class="lib-nav">
          <button
            v-if="canCreateLibrary"
            type="button"
            class="lib-add"
            @click="openCreateLibrary"
          >
            <el-icon><Plus /></el-icon>
            新建知识库
          </button>

          <div v-loading="loading" class="lib-nav-list">
            <div v-if="!librariesForTab.length" class="lib-nav-empty">
              <p>暂无知识库</p>
              <el-button
                v-if="canCreateLibrary"
                link
                type="primary"
                @click="openCreateLibrary"
              >
                立即创建
              </el-button>
            </div>

            <button
              v-for="ds in librariesForTab"
              :key="ds.id"
              type="button"
              class="lib-nav-item"
              :class="{ active: selectedDatasetId === ds.id }"
              @click="selectedDatasetId = ds.id"
            >
              <el-icon class="lib-nav-icon">
                <FolderOpened v-if="selectedDatasetId === ds.id" />
                <Folder v-else />
              </el-icon>
              <span class="lib-nav-name">{{ ds.name }}</span>
              <span class="lib-nav-count">{{ ds.document_count ?? 0 }}</span>
              <el-dropdown
                v-if="canManageLibrary(ds)"
                trigger="click"
                @click.stop
                @command="
                  (cmd: string) =>
                    cmd === 'edit' ? openEditLibrary(ds) : removeLibrary(ds)
                "
              >
                <el-icon class="lib-nav-more" @click.stop><MoreFilled /></el-icon>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">重命名</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </button>
          </div>
        </aside>

        <!-- 右侧内容 -->
        <section class="doc-content">
          <template v-if="selectedDataset">
            <div class="content-toolbar">
              <div class="content-head">
                <h2>{{ selectedDataset.name }}</h2>
                <p v-if="selectedDataset.description">{{ selectedDataset.description }}</p>
                <p v-else class="muted">PDF · DOCX · MD · TXT · HTML</p>
              </div>
              <div class="content-actions">
                <el-select
                  v-model="docTypeFilter"
                  placeholder="类型"
                  clearable
                  size="default"
                  class="type-select"
                >
                  <el-option
                    v-for="t in docTypeOptions"
                    :key="t.id"
                    :label="t.label"
                    :value="t.id"
                  />
                </el-select>
                <el-button :icon="Refresh" :loading="loading" @click="loadDocuments" />
                <el-button
                  v-if="canUploadDocuments"
                  type="primary"
                  :icon="Upload"
                  @click="openUploadDialog"
                >
                  上传
                </el-button>
              </div>
            </div>

            <div v-loading="loading" class="content-body">
              <el-empty
                v-if="!documents.length"
                :image-size="64"
                description="暂无文档，上传后将自动解析入库"
              >
                <el-button
                  v-if="canUploadDocuments"
                  type="primary"
                  :icon="Upload"
                  @click="openUploadDialog"
                >
                  上传文档
                </el-button>
              </el-empty>

              <template v-else>
                <el-table
                  :data="documents"
                  class="doc-table"
                  :row-class-name="({ row }) => rowStatusClass(row.status)"
                  @row-click="(row: DocumentItem) => openDetail(row.id)"
                >
                  <el-table-column label="文档" min-width="280">
                    <template #default="{ row }">
                      <div class="cell-file">
                        <span class="ext-tag" :class="fileExtClass(row.title)">
                          {{ fileExt(row.title) }}
                        </span>
                        <span class="file-name" :title="row.title">{{ row.title }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="类型" width="100">
                    <template #default="{ row }">
                      {{ docTypeLabel(String(row.metadata?.doc_type || "")) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="状态" width="100">
                    <template #default="{ row }">
                      <DocStatusTag :status="row.status" />
                    </template>
                  </el-table-column>
                  <el-table-column label="上传时间" width="148">
                    <template #default="{ row }">
                      <span class="time-cell">{{ formatShortDate(row.created_at) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="" width="148" fixed="right" align="right">
                    <template #default="{ row }">
                      <div class="cell-actions" @click.stop>
                        <el-button link type="primary" @click="openDetail(row.id)">
                          详情
                        </el-button>
                        <el-button
                          link
                          type="primary"
                          @click="router.push(`/documents/${row.id}/chunks`)"
                        >
                          文本块
                        </el-button>
                        <el-dropdown
                          v-if="canManageDoc(row)"
                          trigger="click"
                          @command="(cmd: string) => handleDocAction(cmd, row)"
                        >
                          <el-button link type="primary">
                            <el-icon><MoreFilled /></el-icon>
                          </el-button>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item command="reindex">重新索引</el-dropdown-item>
                              <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="table-footer">
                  <el-pagination
                    v-model:current-page="page"
                    v-model:page-size="pageSize"
                    :total="total"
                    :page-sizes="[10, 20, 50]"
                    layout="total, sizes, prev, pager, next"
                    background
                    small
                    @current-change="onPageChange"
                    @size-change="onPageSizeChange"
                  />
                </div>
              </template>
            </div>
          </template>

          <div v-else class="content-empty">
            <el-empty description="选择左侧知识库，或创建一个新的">
              <el-button
                v-if="canCreateLibrary"
                type="primary"
                :icon="Plus"
                @click="openCreateLibrary"
              >
                新建知识库
              </el-button>
            </el-empty>
          </div>
        </section>
      </div>
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
                支持 PDF · DOCX · MD · TXT · HTML，单次最多
                {{ UPLOAD_FILE_LIMIT }} 个
              </p>
            </div>
          </el-upload>

          <ul v-if="pendingFiles.length" class="batch-file-list">
            <li
              v-for="(file, index) in pendingFiles"
              :key="`${file.name}-${file.size}-${index}`"
              class="file-preview-card"
            >
              <div class="file-preview-badge" :class="fileExtClass(file.name)">
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
            确认上传{{
              pendingFiles.length ? `（${pendingFiles.length}）` : ""
            }}
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
            <div
              v-else-if="detailDoc.status === 'failed'"
              class="detail-empty detail-empty-error"
            >
              <p>文档处理失败，暂无内容</p>
              <pre v-if="detailDoc.error" class="error-text">{{
                detailDoc.error
              }}</pre>
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
                <dd v-if="detailDoc.updated_at">
                  {{ formatTime(detailDoc.updated_at) }}
                </dd>
                <dt v-if="detailDoc.mime_type">文件格式</dt>
                <dd v-if="detailDoc.mime_type">{{ detailDoc.mime_type }}</dd>
                <dt>文档 ID</dt>
                <dd>
                  <code class="detail-id-inline">{{ detailDoc.id }}</code>
                </dd>
              </dl>
            </el-collapse-item>
          </el-collapse>

          <div class="detail-actions">
            <el-button type="primary" @click="goToChunks(detailDoc.id)"
              >文本块管理</el-button
            >
            <template v-if="canManageDoc(detailDoc)">
              <el-button @click="reindex(detailDoc.id)">重新索引</el-button>
              <el-button type="danger" plain @click="remove(detailDoc.id)"
                >删除</el-button
              >
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
  min-width: 0;
  height: calc(100vh - var(--topbar-height) - var(--page-padding-y) * 2);
  min-height: 520px;
}

.docs-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

/* ── 顶栏 ── */
.shell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.header-start {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
}

.shell-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.scope-tabs {
  display: inline-flex;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}

.scope-tab {
  padding: 6px 16px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.scope-tab + .scope-tab {
  border-left: 1px solid var(--border-default);
}

.scope-tab:hover {
  background: var(--brand-sidebar-hover);
}

.scope-tab.active {
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
  font-weight: 600;
}

.header-stats {
  font-size: 13px;
  color: var(--text-muted);
  white-space: nowrap;
}

.header-stats .dot {
  margin: 0 6px;
  opacity: 0.4;
}

.header-stats .ok {
  color: #059669;
}

.header-stats .pending {
  color: #d97706;
}

/* ── 主体分栏 ── */
.shell-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.lib-nav {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-subtle);
  background: #fafaf9;
  min-height: 0;
}

.lib-add {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 12px;
  padding: 8px;
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.lib-add:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary-dark);
  background: #fff;
}

.lib-nav-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
  min-height: 0;
}

.lib-nav-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-muted);
}

.lib-nav-empty p {
  margin: 0 0 8px;
}

.lib-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  margin-bottom: 2px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background 0.12s, color 0.12s;
}

.lib-nav-item:hover {
  background: rgb(255 255 255 / 80%);
  color: var(--text-primary);
}

.lib-nav-item.active {
  background: #fff;
  color: var(--text-primary);
  font-weight: 500;
  box-shadow: var(--shadow-sm);
}

.lib-nav-icon {
  font-size: 16px;
  flex-shrink: 0;
  color: var(--text-muted);
}

.lib-nav-item.active .lib-nav-icon {
  color: var(--brand-primary);
}

.lib-nav-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lib-nav-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--border-subtle);
  padding: 1px 6px;
  border-radius: 10px;
  flex-shrink: 0;
}

.lib-nav-more {
  flex-shrink: 0;
  font-size: 14px;
  color: var(--text-muted);
  padding: 2px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.12s;
}

.lib-nav-item:hover .lib-nav-more {
  opacity: 1;
}

/* ── 右侧内容 ── */
.doc-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.content-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.content-head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.content-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.content-head p.muted {
  color: var(--text-body);
}

.content-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.type-select {
  width: 120px;
}

.content-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 20px 16px;
  overflow: hidden;
}

.content-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── 表格 ── */
.doc-table {
  flex: 1;
  min-height: 0;
  --el-table-border-color: var(--border-subtle);
  --el-table-header-bg-color: #fafaf9;
  --el-table-row-hover-bg-color: #fffbf5;
}

.doc-table :deep(.el-table__inner-wrapper) {
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
}

.doc-table :deep(.el-table__row) {
  cursor: pointer;
}

.doc-table :deep(.row-processing) {
  --el-table-tr-bg-color: #fffbeb;
}

.doc-table :deep(.row-failed) {
  --el-table-tr-bg-color: #fef2f2;
}

.cell-file {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.ext-tag {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.ext-tag.ext-pdf { background: #fef2f2; color: #dc2626; }
.ext-tag.ext-doc { background: #eff6ff; color: #2563eb; }
.ext-tag.ext-md { background: #ecfdf5; color: #059669; }
.ext-tag.ext-html { background: #fff7ed; color: #ea580c; }
.ext-tag.ext-txt { background: #f5f5f4; color: #57534e; }
.ext-tag.ext-default { background: var(--brand-primary-soft); color: var(--brand-primary-dark); }

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: var(--text-primary);
}

.time-cell {
  font-size: 13px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.cell-actions {
  display: inline-flex;
  align-items: center;
  gap: 0;
}

.table-footer {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
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

.detail-file-badge.ext-pdf {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}
.detail-file-badge.ext-doc {
  background: #eff6ff;
  color: #2563eb;
  border-color: #bfdbfe;
}
.detail-file-badge.ext-md {
  background: #ecfdf5;
  color: #059669;
  border-color: #a7f3d0;
}
.detail-file-badge.ext-html {
  background: #fff7ed;
  color: #ea580c;
  border-color: #fed7aa;
}
.detail-file-badge.ext-txt {
  background: #f5f5f4;
  color: #57534e;
  border-color: #e7e5e4;
}
.detail-file-badge.ext-default {
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
  border-color: rgb(249 115 22 / 20%);
}

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

  .shell-body {
    flex-direction: column;
  }

  .lib-nav {
    width: 100%;
    max-height: 200px;
    border-right: none;
    border-bottom: 1px solid var(--border-subtle);
  }

  .shell-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-start {
    flex-wrap: wrap;
  }

  .content-toolbar {
    flex-direction: column;
  }

  .upload-info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
