<template>
  <div class="workstation-layout">
    <div class="app-shell">
      <div class="app-frame">
        <header class="topbar">
          <div class="topbar-left">
            <div class="title-row">
              <div class="app-title">MultiNeiroCreator</div>
            </div>
          </div>

          <div class="topbar-center">
            <ProjectSwitcher
              @create="openCreateProjectDialog"
              @open-picker="handleOpenProjectPicker"
              @open-recent="handleOpenRecentProject"
            />
          </div>

          <div class="topbar-right">
            <div class="status-row">
              <div ref="saveModeWrapRef" class="status-button-wrap">
                <button
                  class="status-button"
                  type="button"
                  :aria-expanded="isSaveModeOpen"
                  @click.stop="isSaveModeOpen = !isSaveModeOpen"
                >
                  <Transition name="save-mode-label" mode="out-in">
                    <span :key="currentSaveModeLabel" class="status-button-label">{{
                      currentSaveModeLabel
                    }}</span>
                  </Transition>
                  <span>▾</span>
                </button>
                <Transition name="panel-float">
                  <div v-if="isSaveModeOpen" class="status-panel">
                    <button
                      v-for="item in saveModeOptions"
                      :key="item.value"
                      class="status-panel-option"
                      type="button"
                      :disabled="isSaveModeApplying"
                      @click="handleSelectSaveMode(item)"
                    >
                      {{ item.label }}
                    </button>
                  </div>
                </Transition>
              </div>
              <button class="status-button" type="button" title="退出登录" @click="handleLogout">
                <span class="status-button-label">退出登录</span>
              </button>
            </div>
            <div class="window-controls" aria-hidden="true">
              <div class="window-dot"></div>
              <div class="window-dot"></div>
              <div class="window-dot"></div>
            </div>
          </div>
        </header>

        <main class="main-grid">
          <aside class="left-column">
            <div class="icon-rail" aria-label="Side navigation">
              <button class="icon-button active" title="Explorer" type="button">☰</button>
              <div class="rail-spacer"></div>
              <button class="icon-button" title="Settings" type="button">⚙</button>
            </div>

            <div class="sidebar-stack">
              <div class="sidebar-workspace">
                <section class="section-card">
                  <div class="section-body">
                    <button class="add-tool-large" type="button" @click="isToolModalOpen = true">
                      添加创作工具 +
                    </button>
                  </div>
                </section>
              </div>
            </div>
          </aside>

          <section class="center-column">
            <div class="canvas-surface">
              <div class="canvas-area">
                <div class="canvas-center">
                  <div class="canvas-callout">创作区，等待加载工具。</div>
                </div>
              </div>
            </div>
          </section>

          <aside class="right-column">
            <AssistantPanel ref="assistantPanelRef" />
          </aside>
        </main>
      </div>
    </div>

    <Transition name="modal-fade">
      <div
        v-if="isToolModalOpen"
        class="modal-overlay"
        :aria-hidden="!isToolModalOpen"
        @click.self="isToolModalOpen = false"
      >
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
          <div class="modal-head">
            <div>
              <div id="modalTitle" class="modal-title">添加工具</div>
              <div class="modal-caption">为当前项目追加新的创作模块或 Agent 插件。</div>
            </div>
            <button
              class="modal-close"
              type="button"
              aria-label="Close"
              @click="isToolModalOpen = false"
            >
              ✕
            </button>
          </div>
          <div class="modal-body">
            <button
              v-for="item in toolModalOptions"
              :key="item.title"
              class="modal-option"
              type="button"
            >
              <div class="message-title">{{ item.title }}</div>
              <div class="modal-option-sub">{{ item.description }}</div>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <CreateProjectDialog
      :open="isCreateProjectModalOpen"
      @close="isCreateProjectModalOpen = false"
      @created="handleProjectCreated"
    />

    <Transition name="modal-fade">
      <div
        v-if="isProjectWarningOpen"
        class="modal-overlay"
        :aria-hidden="!isProjectWarningOpen"
        @click.self="isProjectWarningOpen = false"
      >
        <div
          class="modal-card project-warning-modal"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="projectWarningTitle"
        >
          <div class="modal-head">
            <div>
              <div id="projectWarningTitle" class="modal-title">{{ projectWarningTitle }}</div>
            </div>
          </div>
          <div class="modal-body project-create-body">
            <div class="warning-callout">
              <div class="warning-icon" aria-hidden="true">!</div>
              <div class="warning-content">
                <div class="warning-title">{{ projectWarningTitle }}</div>
                <div class="warning-message">{{ projectWarningMessage }}</div>
              </div>
            </div>
            <div class="project-warning-actions">
              <button
                class="project-danger-button"
                type="button"
                @click="isProjectWarningOpen = false"
              >
                确定
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
// 工作站布局（D1 拆分完成后的形态）：只保留布局骨架与流程协调——
// 入口初始化（路由项目 id -> 服务端详情 -> store）、项目打开/新建/切换导航、
// 保存模式切换、登出。项目/会话状态在 Pinia（stores/project.ts、stores/chat.ts），
// 具体交互在 components/project/*、components/assistant/* 与 composables/*。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from '@/utils/toast'
import { getProject } from '@/serve/project'
import { useLoadingStore } from '@/stores/loading'
import { useUserStore } from '@/stores/user'
import { normalizeSaveMode, useProjectStore, type RecentProjectItem } from '@/stores/project'
import { useChatStore } from '@/stores/chat'
import {
  saveModeLabels,
  saveModeOptions,
  useAutoSave,
  type SaveModeOption,
} from '@/composables/useAutoSave'
import {
  isDirectoryPickerSupported,
  readProjectDirectory,
  requestProjectDirectoryHandle,
  type BrowserDirectoryHandle,
} from '@/utils/localProject'
import ProjectSwitcher from '@/components/project/ProjectSwitcher.vue'
import CreateProjectDialog from '@/components/project/CreateProjectDialog.vue'
import AssistantPanel from '@/components/assistant/AssistantPanel.vue'
import '@/views/workstation/styles/workstation-base.css'

interface ToolModalOption {
  title: string
  description: string
}

// 真实进度接管：让工作站初始化阶段能推动 loadingStore.setProgress()，
// 覆盖层在 realProgress > 0 时无缝从内置 rAF 切到真实进度。
const loadingStore = useLoadingStore()
const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const chatStore = useChatStore()
const autoSave = useAutoSave()

// emit:ready —— 核心资源初始化完成时通知外层淡出覆盖层。
// 该事件与"是否加载成功"解耦（成功/失败都会发出），由父级 Workstation.vue 负责真正收起。
const emit = defineEmits<{ (e: 'ready'): void }>()

const assistantPanelRef = ref<InstanceType<typeof AssistantPanel> | null>(null)
const saveModeWrapRef = ref<HTMLElement | null>(null)

const isToolModalOpen = ref(false)
const isSaveModeOpen = ref(false)
const isSaveModeApplying = ref(false)
const isCreateProjectModalOpen = ref(false)
const isProjectWarningOpen = ref(false)
const projectWarningTitle = ref('')
const projectWarningMessage = ref('')

const toolModalOptions: ToolModalOption[] = [
  {
    title: 'Plugin Module',
    description: '挂载新的创作能力，例如编曲、混音、PV 或 Live2D Agent。',
  },
  {
    title: 'Import Workflow',
    description: '导入已有工作流模板，把当前项目接入新的流水线。',
  },
  {
    title: 'Create Sandbox',
    description: '建立独立实验区，用于测试新模型、新参数和新模块。',
  },
]

const currentSaveModeLabel = computed(() => saveModeLabels[projectStore.saveMode])

/* ---------- 项目打开 / 新建 / 切换 ---------- */

function openProjectWarning(title: string, message: string) {
  projectWarningTitle.value = title
  projectWarningMessage.value = message
  isProjectWarningOpen.value = true
}

function getRouteProjectId() {
  if (typeof route.query.project !== 'string') return null
  if (route.query.project === 'default') return null

  const routeProjectId = Number(route.query.project)
  return Number.isInteger(routeProjectId) && routeProjectId > 0 ? routeProjectId : null
}

/**
 * 以路由为真源导航到目标项目：query 变化时由 Workstation.vue 的 :key 触发重挂载，
 * 新实例走 initializeWorkspaceFromEntryPoint；query 相同则原地重置会话面板。
 */
async function navigateToProject(projectId: number | null) {
  const currentProjectQuery = typeof route.query.project === 'string' ? route.query.project : null
  const nextProjectQuery = projectId != null ? String(projectId) : 'default'
  if (currentProjectQuery === nextProjectQuery) {
    chatStore.resetForProjectSwitch()
    void loadAgentPanel()
    return
  }

  await router.replace({
    path: '/workstation',
    query: { project: nextProjectQuery },
  })
}

/** 项目打开后的统一收口：写 store、同步定时器、重置会话、导航 */
function applyOpenedProject(
  project: { id?: number; name: string; projectPath: string; saveMode: string },
  directoryHandle: BrowserDirectoryHandle | null = null,
) {
  const saveMode = normalizeSaveMode(project.saveMode)
  projectStore.setActiveProject(
    {
      id: project.id ?? null,
      name: project.name,
      projectPath: project.projectPath,
      saveMode,
    },
    directoryHandle,
  )
  autoSave.syncTimer(saveMode)
  chatStore.resetForProjectSwitch()

  projectStore.upsertRecentProject({
    id: project.id ?? projectStore.nextLocalProjectId(),
    title: project.name,
    meta: `最近打开 · 刚刚 · ${project.projectPath}`,
    projectPath: project.projectPath,
    saveMode,
  })
  void navigateToProject(projectStore.id)
}

function openCreateProjectDialog() {
  isCreateProjectModalOpen.value = true
}

function handleProjectCreated(payload: {
  id: number | null
  name: string
  projectPath: string
  directoryHandle: BrowserDirectoryHandle
}) {
  isCreateProjectModalOpen.value = false
  applyOpenedProject(
    {
      id: payload.id ?? undefined,
      name: payload.name,
      projectPath: payload.projectPath,
      saveMode: 'manual',
    },
    payload.directoryHandle,
  )
}

async function handleOpenProjectPicker() {
  if (!isDirectoryPickerSupported()) {
    openProjectWarning('当前浏览器不支持', '请选择 Chromium 内核浏览器后再打开本地项目文件夹。')
    return
  }

  try {
    const directoryHandle = await requestProjectDirectoryHandle()
    const project = await readProjectDirectory(directoryHandle)
    applyOpenedProject(project, directoryHandle)
    ElMessage.success(`已打开项目：${project.name}`)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return

    if (error instanceof Error) {
      if (error.message === 'USER_CANCELLED_DIRECTORY_PICKER') return
      if (error.message === 'INVALID_PROJECT_DIRECTORY') {
        openProjectWarning('项目文件不合法', '所选文件夹中未找到可用的 `project.json` 项目文件。')
        return
      }
      if (error.message === 'INVALID_PROJECT_FILE') {
        openProjectWarning(
          '项目文件不合法',
          '检测到 `project.json`，但内容格式不符合当前项目要求。',
        )
        return
      }
    }

    openProjectWarning('打开项目失败', '本地项目读取失败，请重新选择一个有效的项目文件夹。')
  }
}

function handleOpenRecentProject(item: RecentProjectItem) {
  applyOpenedProject({
    id: item.id > 0 ? item.id : undefined,
    name: item.title,
    projectPath: item.projectPath,
    saveMode: item.saveMode,
  })
  ElMessage.success(`已打开项目：${item.title}`)
}

/**
 * 入口初始化（B3 的修复结论）：URL 项目 id 是更高优先级的真源，
 * 先按 id 调服务端详情恢复元数据；只有路由不可用时才回退本地缓存。
 */
async function initializeWorkspaceFromEntryPoint() {
  const routeProjectId = getRouteProjectId()
  if (routeProjectId !== null) {
    try {
      const { project } = await getProject(routeProjectId)
      applyOpenedProject({
        id: project.id,
        name: project.name,
        projectPath: project.project_path,
        saveMode: project.save_mode,
      })
      return
    } catch {
      // 路由里的项目可能已被删除或无权访问，回退到本地缓存。
    }
  }

  if (projectStore.restoreFromStorage()) {
    autoSave.syncTimer(projectStore.saveMode)
  }
  void loadAgentPanel()
}

/* ---------- 会话面板加载（真实进度接管 + ready 通知） ---------- */

async function loadAgentPanel() {
  try {
    loadingStore.setProgress(35)
    loadingStore.setLabel('Loading conversation history')
    await assistantPanelRef.value?.loadHistory()
    loadingStore.setProgress(95)
    loadingStore.setLabel('Finalizing')
  } catch {
    chatStore.clearMessages()
    loadingStore.setProgress(95)
    loadingStore.setLabel('Finalizing')
  } finally {
    loadingStore.setProgress(100)
    loadingStore.setLabel('Entering')
    // 关键：核心资源加载完成（成功或失败都算"完成"）后通知外层淡出覆盖层。
    emit('ready')
  }
}

/* ---------- 保存模式 / 登出 ---------- */

async function handleSelectSaveMode(option: SaveModeOption) {
  if (isSaveModeApplying.value) return

  isSaveModeApplying.value = true
  try {
    const applied = await autoSave.selectSaveMode(option)
    if (applied) {
      isSaveModeOpen.value = false
    }
  } finally {
    isSaveModeApplying.value = false
  }
}

function handleLogout() {
  useUserStore().logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target as Node | null
  if (saveModeWrapRef.value && target && !saveModeWrapRef.value.contains(target)) {
    isSaveModeOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  void initializeWorkspaceFromEntryPoint()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
.app-shell {
  width: max(100%, var(--app-min-width));
  min-width: var(--app-min-width);
  min-height: var(--app-min-height);
  height: max(100vh, var(--app-min-height));
  background: var(--body-bg);
}

.app-frame {
  width: 100%;
  min-width: var(--app-min-width);
  min-height: var(--app-min-height);
  height: 100%;
  background: var(--body-bg);
  overflow: hidden;
  display: grid;
  grid-template-rows: var(--topbar-h) 1fr;
}

.topbar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 16px;
  position: relative;
  min-width: var(--app-min-width);
  padding: 0 18px;
  border-bottom: 1px solid var(--line) !important;
  background: var(--column-bg);
}

.topbar-left,
.topbar-center,
.topbar-right,
.status-row,
.title-row {
  display: flex;
  align-items: center;
  min-width: 0;
}

.topbar-left {
  gap: 0;
}

.title-row {
  gap: 10px;
  min-width: 0;
}

.topbar-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  justify-content: center;
  gap: 12px;
  min-width: 0;
  padding-right: 0;
  z-index: 2;
}

.topbar-right {
  justify-content: flex-end;
  gap: 12px;
  min-width: 0;
  padding-right: 0;
  margin-right: -6px;
}

.topbar-right .window-controls {
  display: none;
}

.status-row {
  gap: 8px;
  flex-wrap: wrap;
  position: relative;
}

.status-button-wrap {
  position: relative;
}

.status-button {
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 124px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.015);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.status-button-label {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}

.status-button:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

.status-button:hover span {
  color: var(--text-primary);
}

.status-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 220px;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border: 1px solid rgba(40, 40, 40, 0.55);
  border-radius: 16px;
  background: rgba(20, 20, 20, 0.98);
  z-index: 30;
  display: flex;
}

.status-panel-option {
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: 16px;
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
}

.save-mode-label-enter-active,
.save-mode-label-leave-active {
  transition:
    opacity 180ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

.save-mode-label-enter-from,
.save-mode-label-leave-to {
  opacity: 0;
  transform: translateY(3px);
}

.save-mode-label-enter-to,
.save-mode-label-leave-from {
  opacity: 1;
  transform: translateY(0);
}

.main-grid {
  min-height: 0;
  height: 100%;
  display: grid;
  min-width: var(--app-min-width);
  grid-template-columns: var(--left-column-w) minmax(716px, 1fr) var(--right-column-w);
  grid-template-areas: 'left center right';
  background: var(--body-bg);
  overflow: hidden;
}

.left-column {
  grid-area: left;
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-columns: 42px 1fr;
  border-right: 1px solid var(--line) !important;
  background: var(--column-bg);
}

.icon-rail {
  padding: 8px 4px;
  border-right: 1px solid var(--line) !important;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--column-bg);
}

.rail-spacer {
  flex: 1;
}

.icon-button {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  color: var(--text-sidebar);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.icon-button:hover,
.icon-button.active {
  background: var(--hover-bg);
  color: #ffffff;
}

.sidebar-stack {
  min-width: 0;
  display: grid;
  grid-template-rows: 1fr;
  gap: 0;
  padding: 6px;
  background: var(--column-bg);
}

.sidebar-workspace {
  min-height: 100%;
  border: 1px solid rgba(40, 40, 40, 0.55);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.015);
  padding: 4px;
  display: flex;
  flex-direction: column;
}

.section-card {
  border-radius: 0;
  background: transparent;
  overflow: hidden;
}

.section-body {
  padding: 0;
}

.add-tool-large {
  width: 100%;
  min-height: 76px;
  border: 1px solid rgba(40, 40, 40, 0.6) !important;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
}

.add-tool-large:hover {
  background: rgba(255, 255, 255, 0.06) !important;
  color: var(--text-primary) !important;
  filter: none !important;
}

.center-column {
  grid-area: center;
  min-width: 0;
  min-height: 0;
  position: relative;
  background: var(--body-bg);
}

.canvas-surface {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  padding: 6px;
  gap: 10px;
}

.canvas-area {
  flex: 1;
  display: flex;
}

.canvas-center {
  width: 100%;
  min-height: 100%;
  border: 1px solid rgba(40, 40, 40, 0.55);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.015);
  justify-content: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 18px;
  color: var(--text-secondary);
}

.canvas-callout {
  padding: 8px 12px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 16px;
  font-weight: 400;
}

.right-column {
  grid-area: right;
  min-width: 0;
  min-height: 0;
  padding: 0;
  border-left: 1px solid var(--line) !important;
  background:
    radial-gradient(circle at top, rgba(255, 255, 255, 0.04), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)), var(--column-bg);
  position: relative;
  overflow: hidden;
}

@media (max-width: 1180px) {
  .app-shell,
  .app-frame,
  .topbar,
  .main-grid {
    min-width: var(--app-min-width);
  }
}
</style>
