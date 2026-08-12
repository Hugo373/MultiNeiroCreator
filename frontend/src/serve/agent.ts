import request from '@/utils/request'
import { API_BASE, TOKEN_KEY } from '@/constants'
import { useUserStore } from '@/stores/user'

export interface AgentAttachmentItem {
  name: string
  kind?: string | null
  badge?: string | null
  meta?: string | null
}

export interface AgentHistoryItem {
  role: 'user' | 'assistant'
  content: string
  attachments?: AgentAttachmentItem[]
}

export interface AgentChatPayload {
  message: string
  // 不再发送 history：对话历史以服务端数据库为唯一真源（A5），由后端按 project_id 重建
  project_id?: number | null
  attachments?: AgentAttachmentItem[]
}

export interface AgentDocumentMutationResponse {
  status: string
  message: string
  deleted_chunks?: number
  chunks_count?: number
}

export async function uploadAgentDocument(file: File, projectId?: number | null) {
  const formData = new FormData()
  formData.append('file', file)
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.post<unknown, AgentDocumentMutationResponse>(`/upload${suffix}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export async function deleteAgentDocument(filename: string, projectId?: number | null) {
  return request.delete<unknown, AgentDocumentMutationResponse>('/documents', {
    data: {
      filename,
      project_id: projectId,
    },
  })
}

export interface AgentToolEvent {
  type: 'tool'
  tool_name: string
}

export interface AgentContentEvent {
  type: 'content'
  content: string
}

export interface AgentDoneEvent {
  type: 'done'
  history: AgentHistoryItem[]
  tool_used: string | null
}

type AgentStreamEvent = AgentToolEvent | AgentContentEvent | AgentDoneEvent

interface AgentStreamHandlers {
  onTool?: (event: AgentToolEvent) => void
  onContent?: (event: AgentContentEvent) => void
  onDone?: (event: AgentDoneEvent) => void
}

// 解析单个 SSE 块并分发事件。单行损坏（坏 JSON / 未知类型）只丢弃该行，
// 绝不向上抛异常中断整个流（B4）：已收到的内容和后续 token 必须保住。
function dispatchSseBlock(block: string, handlers: AgentStreamHandlers) {
  const line = block.split('\n').find((item) => item.startsWith('data: '))

  if (!line) return

  const payloadText = line.slice(6).trim()
  if (!payloadText) return

  let event: AgentStreamEvent
  try {
    event = JSON.parse(payloadText) as AgentStreamEvent
  } catch {
    console.warn('[SSE] 丢弃无法解析的数据行:', payloadText.slice(0, 200))
    return
  }

  if (event.type === 'tool') handlers.onTool?.(event)
  else if (event.type === 'content') handlers.onContent?.(event)
  else if (event.type === 'done') handlers.onDone?.(event)
  else console.warn('[SSE] 忽略未知事件类型:', (event as { type?: string }).type)
}

export const getAgentHistory = (projectId?: number | null) => {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.get<unknown, AgentHistoryItem[]>(`/history${suffix}`)
}

export async function streamAgentChat(
  payload: AgentChatPayload,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
) {
  const token = localStorage.getItem(TOKEN_KEY)
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let detail = '请求失败'

    try {
      const data = (await response.json()) as { detail?: string }
      detail = data.detail || detail
    } catch {
      detail = response.statusText || detail
    }

    if (response.status === 401) {
      // 与 utils/request.ts 保持一致：只清用户态，不连坐其他 localStorage 数据
      useUserStore().logout()
      window.location.href = '/login'
    }

    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('聊天流初始化失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      dispatchSseBlock(block, handlers)
    }
  }

  if (!buffer.trim()) return

  dispatchSseBlock(buffer, handlers)
}
