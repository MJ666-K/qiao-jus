export const DOC_TYPES = [
  { id: 'law', label: '法律法规', scope: 'platform' },
  { id: 'case', label: '裁判文书/类案', scope: 'platform' },
  { id: 'compliance', label: '合规条款', scope: 'platform' },
  { id: 'contract', label: '合同', scope: 'user' },
  { id: 'dispute', label: '纠纷材料', scope: 'user' },
  { id: 'general', label: '通用文档', scope: 'user' },
  { id: 'report', label: '分析报告', scope: 'generated' },
] as const

/** 系统内部库，不在「我的文档」展示 */
export const SYSTEM_DATASET_NAMES = new Set(['用户报告库'])

export type DocTypeId = (typeof DOC_TYPES)[number]['id']

export function docTypeLabel(id: string | undefined): string {
  return DOC_TYPES.find((t) => t.id === id)?.label ?? id ?? '未知'
}

export function isGeneratedReportDoc(doc: {
  metadata?: Record<string, unknown> | null
  source_uri?: string | null
}): boolean {
  return !!doc.source_uri?.startsWith('report://')
}

export function isUserUploadedDoc(doc: {
  metadata?: Record<string, unknown> | null
  source_uri?: string | null
}): boolean {
  if (isGeneratedReportDoc(doc)) return false
  const dt = String(doc.metadata?.doc_type || 'general')
  return dt !== 'law' && dt !== 'case' && dt !== 'compliance'
}
