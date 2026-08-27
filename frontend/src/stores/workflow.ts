import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { CreativeToolInstance } from './creativeTools'

export type WorkflowCanvasMode = 'select' | 'pan'

export interface WorkflowNode {
  id: string
  toolId: string
  type: CreativeToolInstance['type']
  name: string
  badge: string
  description: string
  color: string
  x: number
  y: number
}

interface WorkflowSnapshot {
  nodes: WorkflowNode[]
}

const STORAGE_KEY = 'mnc-workflow-draft'
const NODE_WIDTH = 236
const NODE_HEIGHT = 116

function cloneNodes(nodes: WorkflowNode[]) {
  return nodes.map((node) => ({ ...node }))
}

function positionForIndex(index: number) {
  return {
    x: 70 + (index % 2) * 280,
    y: 138 + Math.floor(index / 2) * 178,
  }
}

export const useWorkflowStore = defineStore('workflow', () => {
  const nodes = ref<WorkflowNode[]>([])
  const selectedNodeId = ref<string | null>(null)
  const mode = ref<WorkflowCanvasMode>('select')
  const scale = ref(1)
  const offset = ref({ x: 0, y: 0 })
  const undoStack = ref<WorkflowSnapshot[]>([])
  const redoStack = ref<WorkflowSnapshot[]>([])
  let currentStorageKey = STORAGE_KEY

  const selectedNode = computed(
    () => nodes.value.find((node) => node.id === selectedNodeId.value) ?? null,
  )
  const canUndo = computed(() => undoStack.value.length > 0)
  const canRedo = computed(() => redoStack.value.length > 0)

  function persist() {
    localStorage.setItem(
      currentStorageKey,
      JSON.stringify({ nodes: nodes.value, selectedNodeId: selectedNodeId.value }),
    )
  }

  function loadForProject(projectId: number | null) {
    currentStorageKey = projectId == null ? STORAGE_KEY : `${STORAGE_KEY}:${projectId}`
    undoStack.value = []
    redoStack.value = []
    scale.value = 1
    offset.value = { x: 0, y: 0 }
    try {
      const raw = localStorage.getItem(currentStorageKey)
      if (!raw) {
        nodes.value = []
        selectedNodeId.value = null
        return
      }
      const parsed = JSON.parse(raw) as {
        nodes?: WorkflowNode[]
        selectedNodeId?: string | null
      }
      nodes.value = Array.isArray(parsed.nodes) ? parsed.nodes : []
      selectedNodeId.value = parsed.selectedNodeId ?? null
    } catch {
      nodes.value = []
      selectedNodeId.value = null
    }
  }

  function pushUndo(snapshot: WorkflowSnapshot) {
    undoStack.value.push({ nodes: cloneNodes(snapshot.nodes) })
    if (undoStack.value.length > 50) undoStack.value.shift()
    redoStack.value = []
  }

  function addNode(tool: CreativeToolInstance) {
    if (nodes.value.some((node) => node.toolId === tool.id)) return
    const position = positionForIndex(nodes.value.length)
    pushUndo({ nodes: nodes.value })
    nodes.value.push({
      id: `workflow-node-${tool.id}`,
      toolId: tool.id,
      type: tool.type,
      name: tool.name,
      badge: tool.badge,
      description: tool.description,
      color: tool.color,
      ...position,
    })
    selectedNodeId.value = `workflow-node-${tool.id}`
    persist()
  }

  function syncWithTools(tools: CreativeToolInstance[]) {
    const validIds = new Set(tools.map((tool) => tool.id))
    nodes.value = nodes.value.filter((node) => validIds.has(node.toolId))
    for (const tool of tools) {
      if (nodes.value.some((node) => node.toolId === tool.id)) continue
      const position = positionForIndex(nodes.value.length)
      nodes.value.push({
        id: `workflow-node-${tool.id}`,
        toolId: tool.id,
        type: tool.type,
        name: tool.name,
        badge: tool.badge,
        description: tool.description,
        color: tool.color,
        ...position,
      })
    }
    if (selectedNodeId.value && !nodes.value.some((node) => node.id === selectedNodeId.value)) {
      selectedNodeId.value = null
    }
    persist()
  }

  function selectNode(id: string) {
    if (!nodes.value.some((node) => node.id === id)) return
    selectedNodeId.value = id
    persist()
  }

  function moveNode(id: string, x: number, y: number) {
    const node = nodes.value.find((item) => item.id === id)
    if (!node) return
    node.x = Math.round(x)
    node.y = Math.round(y)
    persist()
  }

  function commitNodeMove(before: WorkflowSnapshot) {
    if (JSON.stringify(before.nodes) === JSON.stringify(nodes.value)) return
    pushUndo(before)
    persist()
  }

  function deleteSelected() {
    if (!selectedNodeId.value) return
    const index = nodes.value.findIndex((node) => node.id === selectedNodeId.value)
    if (index < 0) return
    pushUndo({ nodes: nodes.value })
    nodes.value.splice(index, 1)
    selectedNodeId.value = null
    persist()
  }

  function undo() {
    const previous = undoStack.value.pop()
    if (!previous) return
    redoStack.value.push({ nodes: cloneNodes(nodes.value) })
    nodes.value = cloneNodes(previous.nodes)
    selectedNodeId.value = null
    persist()
  }

  function redo() {
    const next = redoStack.value.pop()
    if (!next) return
    undoStack.value.push({ nodes: cloneNodes(nodes.value) })
    nodes.value = cloneNodes(next.nodes)
    selectedNodeId.value = null
    persist()
  }

  function setMode(next: WorkflowCanvasMode) {
    mode.value = next
  }

  function zoomBy(delta: number) {
    scale.value = Math.min(2, Math.max(0.25, Number((scale.value + delta).toFixed(2))))
  }

  function resetView() {
    scale.value = 1
    offset.value = { x: 0, y: 0 }
  }

  function setView(nextScale: number, nextOffset: { x: number; y: number }) {
    scale.value = Math.min(2, Math.max(0.25, nextScale))
    offset.value = nextOffset
  }

  function panBy(dx: number, dy: number) {
    offset.value = { x: offset.value.x + dx, y: offset.value.y + dy }
  }

  return {
    nodes,
    selectedNodeId,
    selectedNode,
    mode,
    scale,
    offset,
    canUndo,
    canRedo,
    nodeWidth: NODE_WIDTH,
    nodeHeight: NODE_HEIGHT,
    loadForProject,
    addNode,
    syncWithTools,
    selectNode,
    moveNode,
    commitNodeMove,
    deleteSelected,
    undo,
    redo,
    setMode,
    zoomBy,
    resetView,
    setView,
    panBy,
  }
})
