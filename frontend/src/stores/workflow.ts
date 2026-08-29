import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { CreativeToolInstance } from './creativeTools'

export type WorkflowCanvasMode = 'select' | 'pan'
export type WorkflowEndpoint = 'input' | 'output'

export const WORKFLOW_INPUT_ID = 'workflow-input'
export const WORKFLOW_OUTPUT_ID = 'workflow-output'

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

export interface WorkflowEdge {
  source: string
  target: string
}

export interface WorkflowEndpointPosition {
  x: number
  y: number
}

export interface WorkflowSnapshot {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  endpointPositions: Partial<Record<WorkflowEndpoint, WorkflowEndpointPosition>>
}

function cloneNodes(nodes: WorkflowNode[]) {
  return nodes.map((node) => ({ ...node }))
}

function cloneEdges(edges: WorkflowEdge[]) {
  return edges.map((edge) => ({ ...edge }))
}

function cloneSnapshot(snapshot: WorkflowSnapshot): WorkflowSnapshot {
  return {
    nodes: cloneNodes(snapshot.nodes),
    edges: cloneEdges(snapshot.edges),
    endpointPositions: { ...snapshot.endpointPositions },
  }
}

function positionForIndex(index: number) {
  return {
    x: 300 + (index % 3) * 300,
    y: 150 + Math.floor(index / 3) * 178,
  }
}

export const useWorkflowStore = defineStore('workflow', () => {
  const nodes = ref<WorkflowNode[]>([])
  const edges = ref<WorkflowEdge[]>([])
  const endpointPositions = ref<Partial<Record<WorkflowEndpoint, WorkflowEndpointPosition>>>({
    input: { x: 36, y: 280 },
  })
  const selectedNodeId = ref<string | null>(null)
  const selectedNodeIds = ref<string[]>([])
  const mode = ref<WorkflowCanvasMode>('select')
  const scale = ref(1)
  const offset = ref({ x: 0, y: 0 })
  const undoStack = ref<WorkflowSnapshot[]>([])
  const redoStack = ref<WorkflowSnapshot[]>([])
  let currentStorageKey = 'mnc-workflow-draft'

  const selectedNode = computed(
    () => nodes.value.find((node) => node.id === selectedNodeId.value) ?? null,
  )
  const canUndo = computed(() => undoStack.value.length > 0)
  const canRedo = computed(() => redoStack.value.length > 0)

  function snapshot(): WorkflowSnapshot {
    return {
      nodes: cloneNodes(nodes.value),
      edges: cloneEdges(edges.value),
      endpointPositions: { ...endpointPositions.value },
    }
  }

  function persist() {
    localStorage.setItem(
      currentStorageKey,
      JSON.stringify({
        nodes: nodes.value,
        edges: edges.value,
        endpointPositions: endpointPositions.value,
        selectedNodeId: selectedNodeId.value,
        selectedNodeIds: selectedNodeIds.value,
      }),
    )
  }

  function clearSelection() {
    selectedNodeId.value = null
    selectedNodeIds.value = []
    persist()
  }

  function loadForProject(projectId: number | null) {
    currentStorageKey = projectId == null ? 'mnc-workflow-draft' : `mnc-workflow-draft:${projectId}`
    undoStack.value = []
    redoStack.value = []
    scale.value = 1
    offset.value = { x: 0, y: 0 }
    try {
      const raw = localStorage.getItem(currentStorageKey)
      if (!raw) {
        nodes.value = []
        edges.value = []
        endpointPositions.value = { input: { x: 36, y: 280 } }
        selectedNodeId.value = null
        selectedNodeIds.value = []
        return
      }
      const parsed = JSON.parse(raw) as {
        nodes?: WorkflowNode[]
        edges?: WorkflowEdge[]
        selectedNodeId?: string | null
        selectedNodeIds?: string[]
        endpointPositions?: Partial<Record<WorkflowEndpoint, WorkflowEndpointPosition>>
      }
      const validNodeIds = new Set((parsed.nodes ?? []).map((node) => node.id))
      nodes.value = Array.isArray(parsed.nodes) ? parsed.nodes : []
      edges.value = Array.isArray(parsed.edges)
        ? parsed.edges
            .filter(
              (edge) =>
                [WORKFLOW_INPUT_ID, WORKFLOW_OUTPUT_ID].includes(edge.source) ||
                validNodeIds.has(edge.source),
            )
            .filter(
              (edge) =>
                [WORKFLOW_INPUT_ID, WORKFLOW_OUTPUT_ID].includes(edge.target) ||
                validNodeIds.has(edge.target),
            )
        : []
      endpointPositions.value = parsed.endpointPositions ?? { input: { x: 36, y: 280 } }
      selectedNodeIds.value = Array.isArray(parsed.selectedNodeIds)
        ? parsed.selectedNodeIds.filter((id) => validNodeIds.has(id))
        : parsed.selectedNodeId && validNodeIds.has(parsed.selectedNodeId)
          ? [parsed.selectedNodeId]
          : []
      selectedNodeId.value = selectedNodeIds.value[selectedNodeIds.value.length - 1] ?? null
    } catch {
      nodes.value = []
      edges.value = []
      endpointPositions.value = { input: { x: 36, y: 280 } }
      selectedNodeId.value = null
      selectedNodeIds.value = []
    }
  }

  function pushUndo(previous: WorkflowSnapshot) {
    undoStack.value.push(cloneSnapshot(previous))
    if (undoStack.value.length > 50) undoStack.value.shift()
    redoStack.value = []
  }

  function addNode(tool: CreativeToolInstance) {
    if (nodes.value.some((node) => node.toolId === tool.id)) return
    const position = positionForIndex(nodes.value.length)
    pushUndo(snapshot())
    const nodeId = `workflow-node-${tool.id}`
    nodes.value.push({
      id: nodeId,
      toolId: tool.id,
      type: tool.type,
      name: tool.name,
      badge: tool.badge,
      description: tool.description,
      color: tool.color,
      ...position,
    })
    selectedNodeId.value = nodeId
    selectedNodeIds.value = [nodeId]
    persist()
  }

  function syncWithTools(tools: CreativeToolInstance[]) {
    const validIds = new Set(tools.map((tool) => tool.id))
    const validNodeIds = new Set(
      nodes.value.filter((node) => validIds.has(node.toolId)).map((node) => node.id),
    )
    nodes.value = nodes.value.filter((node) => validIds.has(node.toolId))
    edges.value = edges.value.filter(
      (edge) =>
        (edge.source === WORKFLOW_INPUT_ID ||
          edge.source === WORKFLOW_OUTPUT_ID ||
          validNodeIds.has(edge.source)) &&
        (edge.target === WORKFLOW_INPUT_ID ||
          edge.target === WORKFLOW_OUTPUT_ID ||
          validNodeIds.has(edge.target)),
    )
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
    const currentIds = new Set(nodes.value.map((node) => node.id))
    selectedNodeIds.value = selectedNodeIds.value.filter((id) => currentIds.has(id))
    selectedNodeId.value = selectedNodeIds.value[selectedNodeIds.value.length - 1] ?? null
    persist()
  }

  function selectNode(id: string, additive = false) {
    if (!nodes.value.some((node) => node.id === id)) return
    if (additive) {
      selectedNodeIds.value = selectedNodeIds.value.includes(id)
        ? selectedNodeIds.value.filter((selectedId) => selectedId !== id)
        : [...selectedNodeIds.value, id]
    } else {
      selectedNodeIds.value = [id]
    }
    selectedNodeId.value = selectedNodeIds.value[selectedNodeIds.value.length - 1] ?? null
    persist()
  }

  function selectNodes(ids: string[]) {
    const validIds = new Set(nodes.value.map((node) => node.id))
    selectedNodeIds.value = ids.filter((id) => validIds.has(id))
    selectedNodeId.value = selectedNodeIds.value[selectedNodeIds.value.length - 1] ?? null
    persist()
  }

  function moveNode(id: string, x: number, y: number) {
    const node = nodes.value.find((item) => item.id === id)
    if (!node) return
    node.x = Math.round(x)
    node.y = Math.round(y)
    persist()
  }

  function moveNodes(moves: { id: string; x: number; y: number }[]) {
    for (const move of moves) {
      const node = nodes.value.find((item) => item.id === move.id)
      if (!node) continue
      node.x = Math.round(move.x)
      node.y = Math.round(move.y)
    }
    persist()
  }

  function moveEndpoint(endpoint: WorkflowEndpoint, x: number, y: number) {
    endpointPositions.value[endpoint] = { x: Math.round(x), y: Math.round(y) }
    persist()
  }

  function commitEndpointMove(previous: WorkflowSnapshot) {
    if (JSON.stringify(previous.endpointPositions) === JSON.stringify(endpointPositions.value))
      return
    pushUndo(previous)
    persist()
  }

  function commitNodeMove(previous: WorkflowSnapshot) {
    if (JSON.stringify(previous) === JSON.stringify(snapshot())) return
    pushUndo(previous)
    persist()
  }

  function removeNodes(ids: string[]) {
    const removeIds = new Set(ids)
    if (!removeIds.size) return
    const hasNode = nodes.value.some((node) => removeIds.has(node.id))
    if (!hasNode) return
    pushUndo(snapshot())
    nodes.value = nodes.value.filter((node) => !removeIds.has(node.id))
    edges.value = edges.value.filter(
      (edge) => !removeIds.has(edge.source) && !removeIds.has(edge.target),
    )
    selectedNodeIds.value = selectedNodeIds.value.filter((id) => !removeIds.has(id))
    selectedNodeId.value = selectedNodeIds.value[selectedNodeIds.value.length - 1] ?? null
    persist()
  }

  function removeNode(id: string) {
    removeNodes([id])
  }

  function removeNodeByToolId(toolId: string) {
    const node = nodes.value.find((item) => item.toolId === toolId)
    if (node) removeNode(node.id)
  }

  function deleteSelected() {
    removeNodes(selectedNodeIds.value)
  }

  function wouldCreateCycle(source: string, target: string) {
    const visited = new Set<string>()
    const pending = [target]
    while (pending.length) {
      const current = pending.pop()
      if (!current || visited.has(current)) continue
      if (current === source) return true
      visited.add(current)
      for (const edge of edges.value) {
        if (edge.source === current) pending.push(edge.target)
      }
    }
    return false
  }

  function addConnection(source: string, target: string) {
    const validIds = new Set(nodes.value.map((node) => node.id))
    const isValidSource = source === WORKFLOW_INPUT_ID || validIds.has(source)
    const isValidTarget = target === WORKFLOW_OUTPUT_ID || validIds.has(target)
    if (!isValidSource || !isValidTarget || source === target) return false
    if (source === WORKFLOW_OUTPUT_ID || target === WORKFLOW_INPUT_ID) return false
    if (edges.value.some((edge) => edge.source === source && edge.target === target)) return false
    // 第一版只允许一个主输入，避免无意中产生图上的合并；同一输出可以连接多个下游节点。
    if (target !== WORKFLOW_OUTPUT_ID && edges.value.some((edge) => edge.target === target)) {
      return false
    }
    if (wouldCreateCycle(source, target)) return false
    pushUndo(snapshot())
    edges.value.push({ source, target })
    persist()
    return true
  }

  function removeConnection(source: string, target: string) {
    const index = edges.value.findIndex((edge) => edge.source === source && edge.target === target)
    if (index < 0) return
    pushUndo(snapshot())
    edges.value.splice(index, 1)
    persist()
  }

  function undo() {
    const previous = undoStack.value.pop()
    if (!previous) return
    redoStack.value.push(snapshot())
    nodes.value = cloneNodes(previous.nodes)
    edges.value = cloneEdges(previous.edges)
    endpointPositions.value = { ...previous.endpointPositions }
    selectedNodeIds.value = []
    selectedNodeId.value = null
    persist()
  }

  function redo() {
    const next = redoStack.value.pop()
    if (!next) return
    undoStack.value.push(snapshot())
    nodes.value = cloneNodes(next.nodes)
    edges.value = cloneEdges(next.edges)
    endpointPositions.value = { ...next.endpointPositions }
    selectedNodeIds.value = []
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
    edges,
    endpointPositions,
    selectedNodeId,
    selectedNodeIds,
    selectedNode,
    mode,
    scale,
    offset,
    canUndo,
    canRedo,
    nodeWidth: 236,
    nodeHeight: 116,
    loadForProject,
    addNode,
    syncWithTools,
    selectNode,
    selectNodes,
    clearSelection,
    moveNode,
    moveNodes,
    commitNodeMove,
    moveEndpoint,
    commitEndpointMove,
    removeNode,
    removeNodes,
    removeNodeByToolId,
    deleteSelected,
    addConnection,
    removeConnection,
    undo,
    redo,
    setMode,
    zoomBy,
    resetView,
    setView,
    panBy,
  }
})
