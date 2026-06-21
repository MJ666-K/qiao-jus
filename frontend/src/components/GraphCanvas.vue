<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import type { GraphEdge, GraphNode } from '@/types'

type SimNode = GraphNode & d3.SimulationNodeDatum

const props = defineProps<{
  entities: GraphNode[]
  relations: GraphEdge[]
}>()

const containerRef = ref<HTMLDivElement>()
let simulation: d3.Simulation<SimNode, d3.SimulationLinkDatum<SimNode>> | null = null

function render() {
  const el = containerRef.value
  if (!el) return
  el.innerHTML = ''
  if (!props.entities.length) return

  const width = el.clientWidth || 640
  const height = 480

  const svg = d3
    .select(el)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  const nodes: SimNode[] = props.entities.map((e) => ({ ...e }))
  const links = props.relations.map((r) => ({ ...r }))

  const color = d3.scaleOrdinal(d3.schemeCategory10)

  simulation = d3
    .forceSimulation(nodes)
    .force('charge', d3.forceManyBody().strength(-180))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(36))

  if (links.length) {
    simulation.force(
      'link',
      d3
        .forceLink<SimNode, d3.SimulationLinkDatum<SimNode>>(links)
        .id((d) => d.id)
        .distance(90),
    )
  }

  const link = svg
    .append('g')
    .selectAll('line')
    .data(links)
    .enter()
    .append('line')
    .attr('stroke', '#94a3b8')
    .attr('stroke-opacity', 0.6)

  const node = svg
    .append('g')
    .selectAll<SVGGElement, SimNode>('g')
    .data(nodes)
    .enter()
    .append('g')

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

  node
    .append('circle')
    .attr('r', 10)
    .attr('fill', (d) => color(String(d.type || 'default')))

  node
    .append('text')
    .text((d) => d.name)
    .attr('dx', 14)
    .attr('dy', 4)
    .attr('font-size', 12)
    .attr('fill', '#334155')

  simulation.on('tick', () => {
    link
      .attr('x1', (d) => nodeCoord(d.source).x)
      .attr('y1', (d) => nodeCoord(d.source).y)
      .attr('x2', (d) => nodeCoord(d.target).x)
      .attr('y2', (d) => nodeCoord(d.target).y)
    node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
  })
}

function nodeCoord(endpoint: SimNode | string): { x: number; y: number } {
  if (typeof endpoint === 'string') return { x: 0, y: 0 }
  return { x: endpoint.x ?? 0, y: endpoint.y ?? 0 }
}

watch(() => [props.entities, props.relations], render, { deep: true })
onMounted(render)
onUnmounted(() => simulation?.stop())
</script>

<template>
  <div ref="containerRef" class="graph-canvas">
    <div v-if="!entities.length" class="empty">暂无图谱数据</div>
  </div>
</template>

<style scoped>
.graph-canvas {
  min-height: 480px;
  background: #f8fafc;
  border-radius: 8px;
  position: relative;
}

.empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #94a3b8;
}
</style>
