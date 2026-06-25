import { defineStore } from 'pinia'
import { ref } from 'vue'
import { analyzeReport, getReport, listReports } from '@/api/reports'
import type { AnalyzeRequest, Report, ReportType } from '@/types'

export const useReportsStore = defineStore('reports', () => {
  const reports = ref<Report[]>([])
  const currentReport = ref<Report | null>(null)
  const loading = ref(false)
  const generating = ref(false)
  const error = ref<string | null>(null)

  async function loadList() {
    loading.value = true
    error.value = null
    try {
      reports.value = await listReports()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function loadOne(id: string) {
    loading.value = true
    error.value = null
    try {
      currentReport.value = await getReport(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
    } finally {
      loading.value = false
    }
    return currentReport.value
  }

  async function triggerAnalyze(
    docIds: string | string[],
    reportType?: ReportType,
  ): Promise<Report> {
    generating.value = true
    error.value = null
    const ids = (Array.isArray(docIds) ? docIds : [docIds]).filter(Boolean)
    const payload: AnalyzeRequest = ids.length > 1
      ? { source_doc_ids: ids }
      : ids.length === 1
        ? { source_doc_id: ids[0] }
        : {}
    if (reportType) payload.report_type = reportType
    try {
      const r = await analyzeReport(payload)
      currentReport.value = r
      return r
    } catch (e) {
      error.value = e instanceof Error ? e.message : '触发分析失败'
      throw e
    } finally {
      generating.value = false
    }
  }

  async function pollUntilDone(id: string, timeoutMs = 90_000): Promise<Report> {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      const r = await getReport(id)
      currentReport.value = r
      if (r.status === 'done') return r
      if (r.status === 'failed') {
        throw new Error(r.error || '报告生成失败')
      }
      await new Promise((resolve) => setTimeout(resolve, 2000))
    }
    throw new Error('报告生成超时')
  }

  return {
    reports,
    currentReport,
    loading,
    generating,
    error,
    loadList,
    loadOne,
    triggerAnalyze,
    pollUntilDone,
  }
})
