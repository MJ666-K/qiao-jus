<script setup lang="ts">
import { onMounted } from "vue";
import { Collection } from "@element-plus/icons-vue";
import { useKnowledgeContextStore } from "@/stores/knowledgeContext";
import { docTypeLabel } from "@/constants/docTypes";

withDefaults(
  defineProps<{
    size?: "small" | "default" | "large";
    width?: string;
    showIcon?: boolean;
  }>(),
  {
    size: "small",
    width: "260px",
    showIcon: true,
  },
);

const emit = defineEmits<{
  change: [datasetId: string];
}>();

const kb = useKnowledgeContextStore();

function onChange(id: string) {
  kb.setDataset(id);
  emit("change", id);
}

onMounted(() => {
  void kb.loadDatasets();
});
</script>

<template>
  <div class="dataset-scope-select">
    <el-icon v-if="showIcon" class="scope-icon"><Collection /></el-icon>
    <span v-if="showIcon" class="scope-label">知识库：</span>
    <el-select
      :model-value="kb.selectedDatasetId"
      placeholder="选择知识库"
      :size="size"
      :loading="kb.loading"
      filterable
      :style="{ width }"
      @change="onChange"
    >
      <el-option-group v-if="kb.userDatasets.length" label="私有知识库">
        <el-option
          v-for="ds in kb.userDatasets"
          :key="ds.id"
          :label="ds.name"
          :value="ds.id"
        >
          <span>{{ ds.name }}</span>
          <span class="opt-meta">{{
            docTypeLabel(String(ds.metadata?.doc_type || ""))
          }}</span>
        </el-option>
      </el-option-group>
      <el-option-group v-if="kb.platformDatasets.length" label="平台公共库">
        <el-option
          v-for="ds in kb.platformDatasets"
          :key="ds.id"
          :label="ds.name"
          :value="ds.id"
        >
          <span>{{ ds.name }}</span>
          <span class="opt-meta">{{
            docTypeLabel(String(ds.metadata?.doc_type || ""))
          }}</span>
        </el-option>
      </el-option-group>
    </el-select>
  </div>
</template>

<style scoped>
.dataset-scope-select {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.scope-icon {
  color: var(--brand-primary);
  font-size: 16px;
}

.scope-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.opt-meta {
  float: right;
  font-size: 11px;
  color: var(--text-muted);
}
</style>
