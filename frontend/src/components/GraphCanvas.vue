<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import type { GraphEdge, GraphNode } from '@/types'

type SimNode = GraphNode & d3.SimulationNodeDatum
type SimLink = d3.SimulationLinkDatum<SimNode> & GraphEdge & { key: string }

const props = withDefaults(
  defineProps<{
    graphEntities: GraphNode[]
    graphRelations: GraphEdge[]
    linkMode?: boolean
    selectedEntityId?: string | null
    selectedRelationKey?: string | null
  }>(),
  {
    graphEntities: () => [],
    graphRelations: () => [],
    linkMode: false,
    selectedEntityId: null,
    selectedRelationKey: null,
  },
)

const emit = defineEmits<{
  createRelation: [payload: { source: string; target: string }]
  selectEntity: [id: string]
  selectRelation: [payload: GraphEdge]
}>()

const svgHostRef = ref<HTMLDivElement>()
let simulation: d3.Simulation<SimNode, SimLink> | null = null
let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let svgEl: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
const linkSourceId = ref<string | null>(null)

const NODE_R = 12
const ARROW_PAD = 4

function linkEndpoints(d: SimLink) {
  const sx = nodeCoord(d.source).x
  const sy = nodeCoord(d.source).y
  const tx = nodeCoord(d.target).x
  const ty = nodeCoord(d.target).y
  const dx = tx - sx
  const dy = ty - sy
  const dist = Math.hypot(dx, dy) || 1
  const pad = NODE_R + ARROW_PAD
  return {
    x1: sx + (dx / dist) * pad,
    y1: sy + (dy / dist) * pad,
    x2: tx - (dx / dist) * pad,
    y2: ty - (dy / dist) * pad,
    mx: (sx + tx) / 2,
    my: (sy + ty) / 2,
  }
}

function linkLabel(d: SimLink) {
  const t = d.type?.trim()
  if (t && t !== 'RELATED') return t
  const desc = d.description?.trim()
  if (desc) return desc.length > 12 ? `${desc.slice(0, 12)}…` : desc
  return '关联'
}

function render() {
  const host = svgHostRef.value
  if (!host) return
  simulation?.stop()
  simulation = null
  zoomBehavior = null
  svgEl = null
  linkSourceId.value = null
  host.innerHTML = ''

  const list = props.graphEntities ?? []
  if (!list.length) return

  const width = host.clientWidth || 640
  const height = 480

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  svgEl = svg

  svg
    .append('defs')
    .append('marker')
    .attr('id', 'graph-arrow')
    .attr('viewBox', '0 -4 8 8')
    .attr('refX', 7)
    .attr('refY', 0)
    .attr('markerWidth', 7)
    .attr('markerHeight', 7)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-4 L8,0 L0,4')
    .attr('fill', '#475569')

  const g = svg.append('g')

  zoomBehavior = d3
    .zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.15, 5])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })
  svg.call(zoomBehavior).on('dblclick.zoom', null)

  const nodes: SimNode[] = list.map((e) => ({ ...e }))
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const links: SimLink[] = (props.graphRelations ?? [])
    .filter((r) => nodeById.has(r.source) && nodeById.has(r.target))
    .map((r) => ({
      ...r,
      source: r.source,
      target: r.target,
      key: `${r.source}->${r.target}:${r.type ?? 'RELATED'}`,
    }))

  const color = d3.scaleOrdinal(d3.schemeCategory10)

  simulation = d3
    .forceSimulation(nodes)
    .force('charge', d3.forceManyBody().strength(-240))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(44))
    .alphaDecay(0.08)
    .velocityDecay(0.45)

  if (links.length) {
    simulation.force(
      'link',
      d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(120),
    )
  }

  const link = g
    .append('g')
    .selectAll<SVGPathElement, SimLink>('path')
    .data(links, (d) => d.key)
    .enter()
    .append('path')
    .attr('fill', 'none')
    .attr('stroke', (d) => (d.key === props.selectedRelationKey ? '#2563eb' : '#64748b'))
    .attr('stroke-width', (d) => (d.key === props.selectedRelationKey ? 2.5 : 1.8))
    .attr('marker-end', 'url(#graph-arrow)')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      const src = typeof d.source === 'object' ? (d.source as { id: string }).id : String(d.source)
      const tgt = typeof d.target === 'object' ? (d.target as { id: string }).id : String(d.target)
      emit('selectRelation', {
        source: src,
        target: tgt,
        type: d.type,
        description: d.description,
        weight: d.weight,
      })
    })

  const linkText = g
    .append('g')
    .selectAll<SVGTextElement, SimLink>('text')
    .data(links, (d) => d.key)
    .enter()
    .append('text')
    .text((d) => linkLabel(d))
    .attr('font-size', 10)
    .attr('fill', '#334155')
    .attr('text-anchor', 'middle')
    .attr('dy', -4)
    .style('pointer-events', 'none')

  const node = g
    .append('g')
    .selectAll<SVGGElement, SimNode>('g')
    .data(nodes, (d) => d.id)
    .enter()
    .append('g')
    .style('cursor', 'pointer')

  const drag = d3
    .drag<SVGGElement, SimNode>()
    .on('start', (event, d) => {
      if (!event.active) simulation?.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    })
    .on('drag', (event, d) => {
      d.fx = event.x
      d.fy = event.y
    })
    .on('end', (event, d) => {
      if (!event.active) simulation?.alphaTarget(0)
      d.fx = null
      d.fy = null
    })

  node.call(drag)

  node.on('click', (event, d) => {
    event.stopPropagation()
    emit('selectEntity', d.id)
    if (!props.linkMode) return
    if (!linkSourceId.value) {
      linkSourceId.value = d.id
      highlightNodes(node)
      return
    }
    if (linkSourceId.value === d.id) {
      linkSourceId.value = null
      highlightNodes(node)
      return
    }
    emit('createRelation', { source: linkSourceId.value, target: d.id })
    linkSourceId.value = null
    highlightNodes(node)
  })

  node
    .append('circle')
    .attr('r', NODE_R)
    .attr('fill', (d) => color(String(d.type || 'default')))
    .attr('stroke', (d) => {
      if (linkSourceId.value === d.id) return '#f59e0b'
      if (props.selectedEntityId === d.id) return '#2563eb'
      return '#fff'
    })
    .attr('stroke-width', (d) =>
      linkSourceId.value === d.id || props.selectedEntityId === d.id ? 3 : 2,
    )

  node
    .append('text')
    .text((d) => (d.name.length > 16 ? `${d.name.slice(0, 16)}…` : d.name))
    .attr('dx', 18)
    .attr('dy', 4)
    .attr('font-size', 11)
    .attr('fill', '#334155')

  function highlightNodes(selection: d3.Selection<SVGGElement, SimNode, SVGGElement, unknown>) {
    selection
      .select('circle')
      .attr('stroke', (d) => {
        if (linkSourceId.value === d.id) return '#f59e0b'
        if (props.selectedEntityId === d.id) return '#2563eb'
        return '#fff'
      })
      .attr('stroke-width', (d) =>
        linkSourceId.value === d.id || props.selectedEntityId === d.id ? 3 : 2,
      )
  }

  simulation.on('tick', () => {
    link.attr('d', (d) => {
      const { x1, y1, x2, y2 } = linkEndpoints(d)
      return `M${x1},${y1} L${x2},${y2}`
    })
    linkText.attr('x', (d) => linkEndpoints(d).mx).attr('y', (d) => linkEndpoints(d).my)
    node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
  })

  simulation.on('end', () => simulation?.stop())
}

function nodeCoord(endpoint: SimNode | string | number): { x: number; y: number } {
  if (typeof endpoint === 'object' && endpoint !== null && 'x' in endpoint) {
    return { x: endpoint.x ?? 0, y: endpoint.y ?? 0 }
  }
  return { x: 0, y: 0 }
}

function zoomBy(factor: number) {
  if (!svgEl || !zoomBehavior) return
  svgEl.transition().duration(200).call(zoomBehavior.scaleBy, factor)
}

function resetZoom() {
  if (!svgEl || !zoomBehavior) return
  svgEl.transition().duration(200).call(zoomBehavior.transform, d3.zoomIdentity)
}

defineExpose({ zoomIn: () => zoomBy(1.3), zoomOut: () => zoomBy(0.75), resetZoom })

watch(
  () =>
    [
      props.graphEntities,
      props.graphRelations,
      props.linkMode,
      props.selectedEntityId,
      props.selectedRelationKey,
    ] as const,
  () => render(),
  { deep: true },
)

watch(
  () => props.linkMode,
  (on) => {
    if (!on) linkSourceId.value = null
  },
)

onMounted(() => {
  requestAnimationFrame(render)
})
onUnmounted(() => simulation?.stop())
</script>

<template>
  <div class="graph-canvas">
    <div ref="svgHostRef" class="svg-host" />
    <div v-if="!graphEntities.length" class="empty">暂无数据</div>
  </div>
</template>

<style scoped>
.graph-canvas {
  min-height: 480px;
  background: #f8fafc;
  border-radius: 8px;
  position: relative;
  overflow: hidden;
}

.svg-host {
  width: 100%;
  min-height: 480px;
}

.empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #94a3b8;
  pointer-events: none;
}
</style>
