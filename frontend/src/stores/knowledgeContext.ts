import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { listDatasets } from '@/api/datasets'
import { SYSTEM_DATASET_NAMES } from '@/constants/docTypes'
import type { Dataset } from '@/types'

const STORAGE_KEY = 'kb_scope_dataset_id'

function datasetScope(ds: Dataset): 'user' | 'platform' {
  return String(ds.metadata?.scope || 'user') === 'platform' ? 'platform' : 'user'
}

export const useKnowledgeContextStore = defineStore('knowledgeContext', () => {
  const datasets = ref<Dataset[]>([])
  const loading = ref(false)
  const selectedDatasetId = ref(localStorage.getItem(STORAGE_KEY) || '')

  const selectableDatasets = computed(() =>
    datasets.value.filter(
      (ds) => !SYSTEM_DATASET_NAMES.has(ds.name) && !ds.metadata?.system,
    ),
  )

  const userDatasets = computed(() =>
    selectableDatasets.value.filter((ds) => datasetScope(ds) === 'user'),
  )

  const platformDatasets = computed(() =>
    selectableDatasets.value.filter((ds) => datasetScope(ds) === 'platform'),
  )

  const selectedDataset = computed(
    () => selectableDatasets.value.find((ds) => ds.id === selectedDatasetId.value) ?? null,
  )

  async function loadDatasets() {
    loading.value = true
    try {
      datasets.value = await listDatasets()
      ensureSelection()
    } finally {
      loading.value = false
    }
  }

  function ensureSelection() {
    const valid = selectableDatasets.value.some((ds) => ds.id === selectedDatasetId.value)
    if (valid) return
    const fallback = userDatasets.value[0] || selectableDatasets.value[0]
    setDataset(fallback?.id || '')
  }

  function setDataset(id: string) {
    selectedDatasetId.value = id
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  }

  return {
    datasets,
    loading,
    selectedDatasetId,
    selectableDatasets,
    userDatasets,
    platformDatasets,
    selectedDataset,
    loadDatasets,
    ensureSelection,
    setDataset,
  }
})
