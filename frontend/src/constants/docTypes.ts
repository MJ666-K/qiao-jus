export const DOC_TYPES = [
  { id: 'law', label: '法律法规', scope: 'platform' },
  { id: 'case', label: '裁判文书/类案', scope: 'platform' },
  { id: 'compliance', label: '合规条款', scope: 'platform' },
  { id: 'contract', label: '合同', scope: 'user' },
  { id: 'dispute', label: '纠纷材料', scope: 'user' },
  { id: 'general', label: '通用文档', scope: 'user' },
] as const

export type DocTypeId = (typeof DOC_TYPES)[number]['id']

export function docTypeLabel(id: string | undefined): string {
  return DOC_TYPES.find((t) => t.id === id)?.label ?? id ?? '未知'
}
