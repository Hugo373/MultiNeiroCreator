<template>
  <section
    class="workflow-canvas"
    :class="{ 'is-pan-mode': workflowStore.mode === 'pan' }"
    aria-label="Workflow 工作流画布"
    @wheel.prevent="handleWheel"
    @pointerdown="handleCanvasPointerDown"
  >
    <div
      class="workflow-world"
      :style="{
        transform: `translate(${workflowStore.offset.x}px, ${workflowStore.offset.y}px) scale(${workflowStore.scale})`,
      }"
    >
      <svg class="workflow-connections" aria-hidden="true">
        <path
          v-for="(connection, index) in connections"
          :key="`connection-${index}`"
          :d="connectionPath(connection.from, connection.to)"
        />
      </svg>

      <article
        v-for="(node, index) in workflowStore.nodes"
        :key="node.id"
        class="workflow-node"
        :class="{ 'is-selected': node.id === workflowStore.selectedNodeId }"
        :style="{ left: `${node.x}px`, top: `${node.y}px`, '--node-color': node.color }"
        tabindex="0"
        @pointerdown.stop="startNodeDrag($event, node.id)"
        @click.stop="selectNode(node.id)"
        @keydown.delete.stop="deleteNode(node.id)"
        @keydown.backspace.stop="deleteNode(node.id)"
      >
        <span class="workflow-node-port workflow-node-port-in" aria-hidden="true"></span>
        <span class="workflow-node-port workflow-node-port-out" aria-hidden="true"></span>
        <div class="workflow-node-head">
          <span class="workflow-node-icon">{{ nodeMark(node.type) }}</span>
          <div class="workflow-node-heading">
            <span class="workflow-node-badge">{{ node.badge }}</span>
            <h3>{{ node.name }}</h3>
          </div>
          <span class="workflow-node-number">{{ index + 1 }}</span>
        </div>
        <p>{{ node.description }}</p>
        <div class="workflow-node-footer">预输入节点 · 可拖拽调整位置</div>
      </article>
    </div>

    <div class="workflow-canvas-toolbar" aria-label="画布工具">
      <button
        type="button"
        class="workflow-tool-button workflow-add-button"
        title="添加节点"
        aria-label="添加节点"
        @click.stop="emit('open-picker')"
      >
        +
      </button>
      <span class="workflow-tool-divider"></span>
      <button
        type="button"
        class="workflow-tool-button"
        :class="{ active: workflowStore.mode === 'select' }"
        title="选择和拖拽节点"
        aria-label="选择和拖拽节点"
        @click.stop="workflowStore.setMode('select')"
      >
        ↖
      </button>
      <button
        type="button"
        class="workflow-tool-button"
        :class="{ active: workflowStore.mode === 'pan' }"
        title="平移画布"
        aria-label="平移画布"
        @click.stop="workflowStore.setMode('pan')"
      >
        ✋
      </button>
      <span class="workflow-tool-divider"></span>
      <button
        type="button"
        class="workflow-tool-button"
        title="适应画布"
        aria-label="适应画布"
        @click.stop="workflowStore.resetView()"
      >
        ⛶
      </button>
      <button
        type="button"
        class="workflow-tool-button"
        title="更多画布操作"
        aria-label="更多画布操作"
        @click.stop="toggleMoreMenu"
      >
        …
      </button>
      <div v-if="moreMenuOpen" class="workflow-more-menu" @click.stop>
        <button type="button" @click="resetWorkflow">清空并重新开始</button>
        <button type="button" @click="emit('notify', '复制工作流功能已预留')">复制工作流</button>
        <button type="button" @click="emit('notify', '导出工作流功能已预留')">导出工作流</button>
      </div>
    </div>

    <div class="workflow-history-controls" aria-label="编辑历史">
      <button
        type="button"
        title="撤销"
        aria-label="撤销"
        :disabled="!workflowStore.canUndo"
        @click.stop="workflowStore.undo()"
      >
        ↶
      </button>
      <button
        type="button"
        title="重做"
        aria-label="重做"
        :disabled="!workflowStore.canRedo"
        @click.stop="workflowStore.redo()"
      >
        ↷
      </button>
      <button
        type="button"
        title="操作历史"
        aria-label="操作历史"
        @click.stop="emit('notify', '操作历史面板已预留')"
      >
        ◷
      </button>
    </div>

    <div class="workflow-minimap" aria-label="工作流缩略图">
      <div
        v-for="node in workflowStore.nodes"
        :key="`mini-${node.id}`"
        class="workflow-minimap-node"
        :style="{
          left: `${Math.max(7, node.x / 8)}px`,
          top: `${Math.max(8, node.y / 8)}px`,
          background: node.color,
        }"
      ></div>
    </div>

    <div class="workflow-zoom-controls" aria-label="画布缩放">
      <button type="button" title="缩小" aria-label="缩小" @click.stop="workflowStore.zoomBy(-0.1)">
        −
      </button>
      <button type="button" class="workflow-zoom-value" @click.stop="workflowStore.resetView()">
        {{ Math.round(workflowStore.scale * 100) }}%
      </button>
      <button type="button" title="放大" aria-label="放大" @click.stop="workflowStore.zoomBy(0.1)">
        +
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useWorkflowStore, type WorkflowNode } from '@/stores/workflow'
import type { CreativeToolType } from '@/stores/creativeTools'

const emit = defineEmits<{
  (event: 'open-picker'): void
  (event: 'node-selected', toolId: string): void
  (event: 'notify', message: string): void
}>()

const workflowStore = useWorkflowStore()
const moreMenuOpen = ref(false)
const dragState = ref<{
  id: string
  startX: number
  startY: number
  originX: number
  originY: number
  before: { nodes: WorkflowNode[] }
} | null>(null)
const panState = ref<{ startX: number; startY: number; originX: number; originY: number } | null>(
  null,
)

const connections = computed(() =>
  workflowStore.nodes.slice(1).map((node, index) => ({
    from: workflowStore.nodes[index],
    to: node,
  })),
)

function nodeMark(type: CreativeToolType) {
  return { lyrics: 'Aa', image: '✦', video: '▶', audio: '∿' }[type]
}

function selectNode(id: string) {
  const node = workflowStore.nodes.find((item) => item.id === id)
  if (!node) return
  workflowStore.selectNode(id)
  emit('node-selected', node.toolId)
}

function startNodeDrag(event: PointerEvent, id: string) {
  selectNode(id)
  if (workflowStore.mode !== 'select') return
  const node = workflowStore.nodes.find((item) => item.id === id)
  if (!node) return
  dragState.value = {
    id,
    startX: event.clientX,
    startY: event.clientY,
    originX: node.x,
    originY: node.y,
    before: { nodes: workflowStore.nodes.map((item) => ({ ...item })) },
  }
  window.addEventListener('pointermove', handleNodeDrag)
  window.addEventListener('pointerup', finishNodeDrag, { once: true })
}

function handleNodeDrag(event: PointerEvent) {
  if (!dragState.value) return
  const { id, startX, startY, originX, originY } = dragState.value
  workflowStore.moveNode(
    id,
    originX + (event.clientX - startX) / workflowStore.scale,
    originY + (event.clientY - startY) / workflowStore.scale,
  )
}

function finishNodeDrag() {
  if (dragState.value) workflowStore.commitNodeMove(dragState.value.before)
  dragState.value = null
  window.removeEventListener('pointermove', handleNodeDrag)
}

function handleCanvasPointerDown(event: PointerEvent) {
  if (workflowStore.mode !== 'pan') return
  const target = event.target as HTMLElement | null
  if (target?.closest('button, .workflow-node')) return
  panState.value = {
    startX: event.clientX,
    startY: event.clientY,
    originX: workflowStore.offset.x,
    originY: workflowStore.offset.y,
  }
  window.addEventListener('pointermove', handlePan)
  window.addEventListener('pointerup', finishPan, { once: true })
}

function handlePan(event: PointerEvent) {
  if (!panState.value) return
  workflowStore.setView(workflowStore.scale, {
    x: panState.value.originX + event.clientX - panState.value.startX,
    y: panState.value.originY + event.clientY - panState.value.startY,
  })
}

function finishPan() {
  panState.value = null
  window.removeEventListener('pointermove', handlePan)
}

function handleWheel(event: WheelEvent) {
  workflowStore.zoomBy(event.deltaY > 0 ? -0.05 : 0.05)
}

function connectionPath(from: WorkflowNode, to: WorkflowNode) {
  const startX = from.x + workflowStore.nodeWidth
  const startY = from.y + workflowStore.nodeHeight / 2
  const endX = to.x
  const endY = to.y + workflowStore.nodeHeight / 2
  const bend = Math.max(40, Math.abs(endX - startX) / 2)
  return `M ${startX} ${startY} C ${startX + bend} ${startY}, ${endX - bend} ${endY}, ${endX} ${endY}`
}

function deleteNode(id: string) {
  workflowStore.selectNode(id)
  workflowStore.deleteSelected()
}

function toggleMoreMenu() {
  moreMenuOpen.value = !moreMenuOpen.value
}

function resetWorkflow() {
  moreMenuOpen.value = false
  while (workflowStore.canUndo) workflowStore.undo()
  emit('notify', '工作流画布已清空')
}

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', handleNodeDrag)
  window.removeEventListener('pointermove', handlePan)
})
</script>

<style scoped>
.workflow-canvas {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background-color: #0d0e11;
  background-image: radial-gradient(circle, rgba(148, 163, 184, 0.17) 1px, transparent 1px);
  background-position: 10px 10px;
  background-size: 24px 24px;
  filter: grayscale(1);
  color: #d7d8dc;
  cursor: default;
}

.workflow-canvas.is-pan-mode {
  cursor: grab;
}

.workflow-canvas.is-pan-mode:active {
  cursor: grabbing;
}

.workflow-world {
  position: absolute;
  inset: 0;
  transform-origin: 0 0;
  transition: transform 120ms ease-out;
}

.workflow-connections {
  position: absolute;
  inset: 0;
  width: 2400px;
  height: 1500px;
  overflow: visible;
  pointer-events: none;
}

.workflow-connections path {
  fill: none;
  stroke: #667084;
  stroke-width: 2.5;
  opacity: 0.9;
}

.workflow-node {
  position: absolute;
  width: 236px;
  height: 116px;
  padding: 13px 14px 10px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 13px;
  background: #242529;
  cursor: grab;
  user-select: none;
  transition:
    border-color 160ms ease,
    transform 160ms ease;
}

.workflow-node:hover,
.workflow-node.is-selected {
  border-color: color-mix(in srgb, var(--node-color) 75%, white 5%);
}

.workflow-node.is-selected {
  transform: translateY(-2px);
}

.workflow-node:active {
  cursor: grabbing;
}

.workflow-node-head {
  display: flex;
  align-items: center;
  gap: 9px;
}

.workflow-node-icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 8px;
  background: color-mix(in srgb, var(--node-color) 20%, #27282d);
  color: var(--node-color);
  font-size: 14px;
  font-weight: 600;
}

.workflow-node-heading {
  min-width: 0;
  flex: 1;
}

.workflow-node-badge,
.workflow-node-footer {
  color: #858993;
  font-size: 9px;
}

.workflow-node-heading h3 {
  overflow: hidden;
  margin: 1px 0 0;
  color: #f0f0f1;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-node-number {
  align-self: flex-start;
  color: #777a83;
  font-size: 10px;
}

.workflow-node p {
  display: -webkit-box;
  overflow: hidden;
  margin: 9px 0 0;
  color: #a1a4ad;
  font-size: 10px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.workflow-node-footer {
  margin-top: 5px;
}

.workflow-node-port {
  position: absolute;
  top: 50%;
  width: 6px;
  height: 10px;
  margin-top: -5px;
  border-radius: 2px;
  background: #3b82f6;
}

.workflow-node-port-in {
  left: -4px;
}

.workflow-node-port-out {
  right: -4px;
}

.workflow-canvas-toolbar,
.workflow-history-controls,
.workflow-zoom-controls,
.workflow-minimap {
  position: absolute;
  z-index: 5;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(34, 35, 39, 0.94);
}

.workflow-canvas-toolbar {
  top: 24px;
  left: 18px;
  display: flex;
  width: 42px;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 6px 4px;
  border-radius: 10px;
}

.workflow-tool-button,
.workflow-history-controls button,
.workflow-zoom-controls button {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 6px;
  color: #8d919b;
  font-size: 16px;
}

.workflow-tool-button:hover,
.workflow-tool-button.active,
.workflow-history-controls button:hover:not(:disabled),
.workflow-zoom-controls button:hover {
  background: rgba(255, 255, 255, 0.09);
  color: #f1f2f4;
}

.workflow-add-button {
  color: #d5d7db;
  font-size: 22px;
  font-weight: 300;
}

.workflow-tool-divider {
  width: 25px;
  height: 1px;
  margin: 3px 0;
  background: rgba(255, 255, 255, 0.1);
}

.workflow-more-menu {
  position: absolute;
  top: 4px;
  left: 47px;
  display: grid;
  width: 150px;
  gap: 2px;
  padding: 5px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: #242529;
}

.workflow-more-menu button {
  padding: 7px 8px;
  border-radius: 5px;
  color: #aaaeb7;
  font-size: 10px;
  text-align: left;
}

.workflow-more-menu button:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.workflow-history-controls {
  bottom: 20px;
  left: 18px;
  display: flex;
  gap: 2px;
  padding: 4px;
  border-radius: 9px;
}

.workflow-history-controls button:disabled {
  cursor: not-allowed;
  opacity: 0.3;
}

.workflow-minimap {
  right: 18px;
  bottom: 62px;
  width: 150px;
  height: 90px;
  overflow: hidden;
  border-radius: 8px;
  background: rgba(35, 36, 40, 0.75);
}

.workflow-minimap-node {
  position: absolute;
  width: 24px;
  height: 12px;
  border-radius: 2px;
  opacity: 0.8;
}

.workflow-zoom-controls {
  right: 18px;
  bottom: 20px;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  border-radius: 9px;
}

.workflow-zoom-value {
  width: 52px !important;
  color: #b6bac2 !important;
  font-size: 10px !important;
}
</style>
