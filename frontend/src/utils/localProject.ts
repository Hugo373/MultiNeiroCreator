/**
 * 本地工程文件读写（File System Access API，D1 拆分）。
 * 工程文件只写用户本地磁盘（solved.md 第 6 条的架构决策），后端不碰工程文件。
 */
import { getCurrentTimestampParts } from '@/utils/datetime'

export interface BrowserDirectoryHandle {
  name?: string
  getFileHandle: (name: string, options?: { create?: boolean }) => Promise<BrowserFileHandle>
  getDirectoryHandle: (
    name: string,
    options?: { create?: boolean },
  ) => Promise<BrowserDirectoryHandle>
}

export interface BrowserFileHandle {
  getFile: () => Promise<File>
  createWritable: () => Promise<BrowserWritableFileStream>
}

export interface BrowserWritableFileStream {
  write: (data: string) => Promise<void>
  close: () => Promise<void>
}

export interface ProjectFileContent {
  id?: number
  name: string
  save_mode?: string
  created_at?: string
  updated_at?: string
  version?: string
  last_backup_at?: string
}

export const PROJECT_SUBDIRS = ['assets', 'audio', 'image', 'video', 'exports'] as const

export const USER_CANCELLED_DIRECTORY_PICKER = 'USER_CANCELLED_DIRECTORY_PICKER'

/** 弹出目录选择器；浏览器不支持/用户取消均以 Error 形式抛出 */
export function requestProjectDirectoryHandle(): Promise<BrowserDirectoryHandle> {
  const directoryPicker = (window as Window & {
    showDirectoryPicker?: () => Promise<BrowserDirectoryHandle>
  }).showDirectoryPicker

  if (!directoryPicker) {
    throw new Error('当前浏览器不支持选择文件夹，请使用 Chromium 内核浏览器')
  }

  return directoryPicker().catch(() => {
    throw new Error(USER_CANCELLED_DIRECTORY_PICKER)
  })
}

export function isDirectoryPickerSupported() {
  return typeof (window as Window & { showDirectoryPicker?: unknown }).showDirectoryPicker === 'function'
}

export async function writeLocalJsonFile(
  directoryHandle: BrowserDirectoryHandle,
  fileName: string,
  payload: unknown,
) {
  const fileHandle = await directoryHandle.getFileHandle(fileName, { create: true })
  const writable = await fileHandle.createWritable()
  await writable.write(JSON.stringify(payload, null, 2))
  await writable.close()
}

export async function readLocalProjectMeta(directoryHandle: BrowserDirectoryHandle) {
  try {
    const projectFileHandle = await directoryHandle.getFileHandle('project.json')
    const rawText = await (await projectFileHandle.getFile()).text()
    return JSON.parse(rawText) as Partial<ProjectFileContent>
  } catch {
    return null
  }
}

/** 校验并读取所选文件夹里的 project.json；不合法以特定错误码抛出 */
export async function readProjectDirectory(directoryHandle: BrowserDirectoryHandle) {
  let projectFileHandle: BrowserFileHandle

  try {
    projectFileHandle = await directoryHandle.getFileHandle('project.json')
  } catch {
    throw new Error('INVALID_PROJECT_DIRECTORY')
  }

  try {
    const file = await projectFileHandle.getFile()
    const rawText = await file.text()
    const parsed = JSON.parse(rawText) as Partial<ProjectFileContent>

    if (typeof parsed.name !== 'string' || !parsed.name.trim()) {
      throw new Error('INVALID_PROJECT_FILE')
    }

    return {
      id: typeof parsed.id === 'number' ? parsed.id : undefined,
      name: parsed.name.trim(),
      projectPath: directoryHandle.name || '已选择项目文件夹',
      saveMode: typeof parsed.save_mode === 'string' ? parsed.save_mode : 'manual',
    }
  } catch (error) {
    if (error instanceof Error && error.message === 'INVALID_PROJECT_FILE') {
      throw error
    }

    throw new Error('INVALID_PROJECT_FILE')
  }
}

export function buildAutoSaveProjectName() {
  const now = getCurrentTimestampParts()
  return `未命名项目 ${now.file.replace('_', '-')}`
}

export function buildBackupFileName(projectName: string, timestamp: string) {
  const safeName = projectName.replace(/[<>:"/\\|?*\u0000-\u001f]+/g, '_').trim() || 'project'
  return `${safeName}_${timestamp}.json`
}
