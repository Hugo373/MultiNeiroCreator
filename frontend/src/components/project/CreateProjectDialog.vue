<template>
  <Transition name="modal-fade">
    <div v-if="open" class="modal-overlay" :aria-hidden="!open" @click.self="close">
      <div
        class="modal-card project-create-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="createProjectTitle"
      >
        <div class="modal-head">
          <div>
            <div id="createProjectTitle" class="modal-title">
              {{ step === 1 ? '新建项目' : '保存当前工程' }}
            </div>
            <div class="modal-caption">
              {{
                step === 1
                  ? '先为新的工程文件命名。'
                  : '在进入新项目之前，先确认当前工程的保存方式。'
              }}
            </div>
          </div>
        </div>

        <Transition name="modal-swap" mode="out-in">
          <div v-if="step === 1" key="create-step-1" class="modal-body project-create-body">
            <label class="project-create-label" for="newProjectName">项目名称</label>
            <input
              id="newProjectName"
              v-model="newProjectName"
              class="project-create-input"
              type="text"
              maxlength="120"
              placeholder="请输入新项目名称"
            />
            <div class="project-create-actions">
              <button class="project-secondary-button" type="button" @click="close">取消</button>
              <button class="project-primary-button" type="button" @click="goToStepTwo">
                确定
              </button>
            </div>
          </div>

          <div v-else key="create-step-2" class="modal-body project-create-body">
            <div class="project-create-summary">
              <div class="project-summary-title">是否保存当前工程</div>
              <div class="project-summary-meta">当前工程：{{ projectStore.displayName }}</div>
            </div>
            <div class="project-create-actions project-create-actions--three">
              <button class="project-secondary-button" type="button" @click="step = 1">取消</button>
              <button
                class="project-danger-button"
                type="button"
                @click="isDiscardConfirmOpen = true"
              >
                不保存
              </button>
              <button
                class="project-primary-button"
                type="button"
                :disabled="isCreating"
                @click="saveCurrentAndCreate"
              >
                {{ isCreating ? '处理中...' : '确定' }}
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </Transition>

  <Transition name="modal-fade">
    <div
      v-if="isDiscardConfirmOpen"
      class="modal-overlay"
      :aria-hidden="!isDiscardConfirmOpen"
      @click.self="closeDiscardConfirm"
    >
      <div
        class="modal-card project-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="discardProjectTitle"
      >
        <div class="modal-head">
          <div>
            <div id="discardProjectTitle" class="modal-title">确认不保存</div>
          </div>
        </div>
        <div class="modal-body project-create-body">
          <div class="warning-callout">
            <div class="warning-icon" aria-hidden="true">!</div>
            <div class="warning-content">
              <div class="warning-title">此操作将不保存当前项目所有操作</div>
              <div class="warning-message">确认后将直接进入新项目，当前未落盘内容不会被保留。</div>
            </div>
          </div>
          <div class="project-create-actions">
            <button class="project-secondary-button" type="button" @click="closeDiscardConfirm">
              取消
            </button>
            <button
              class="project-danger-button"
              type="button"
              :disabled="isCreating"
              @click="discardAndCreate"
            >
              {{ isCreating ? '处理中...' : '确定' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
// 新建项目两步弹窗 + 不保存确认（D1 拆分第 6 步，todo §8.4）。
// 本地建目录写 project.json，再向服务端登记元数据换 id；
// 完成后通过 created 事件把新项目快照交给布局层导航。
import { ref, watch } from 'vue'
import { ElMessage } from '@/utils/toast'
import { createProject, type ProjectPayload } from '@/serve/project'
import { getCurrentTimestampParts } from '@/utils/datetime'
import {
  PROJECT_SUBDIRS,
  requestProjectDirectoryHandle,
  writeLocalJsonFile,
  USER_CANCELLED_DIRECTORY_PICKER,
  type BrowserDirectoryHandle,
  type ProjectFileContent,
} from '@/utils/localProject'
import { useProjectStore } from '@/stores/project'

const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{
  (e: 'close'): void
  (
    e: 'created',
    payload: {
      id: number | null
      name: string
      projectPath: string
      directoryHandle: BrowserDirectoryHandle
    },
  ): void
}>()

const projectStore = useProjectStore()

const step = ref<1 | 2>(1)
const newProjectName = ref('')
const isCreating = ref(false)
const isDiscardConfirmOpen = ref(false)

watch(
  () => props.open,
  (opened) => {
    if (opened) {
      step.value = 1
      newProjectName.value = ''
      isDiscardConfirmOpen.value = false
    }
  },
)

function close() {
  if (isCreating.value) return
  isDiscardConfirmOpen.value = false
  emit('close')
}

function closeDiscardConfirm() {
  if (isCreating.value) return
  isDiscardConfirmOpen.value = false
}

function goToStepTwo() {
  if (!newProjectName.value.trim()) {
    ElMessage.warning('请先输入新项目名称')
    return
  }
  step.value = 2
}

/** 旧工程还没有保存位置时，先让用户为它选一个本地文件夹 */
async function ensureCurrentProjectSaved() {
  if (projectStore.projectPath) {
    return
  }

  const handle = await requestProjectDirectoryHandle()
  projectStore.setDirectoryHandle(handle)
  projectStore.setProjectPath(handle?.name || '已选择文件夹')
  ElMessage.success('已选择当前工程保存位置')
}

async function createNamedProject() {
  const projectName = newProjectName.value.trim()
  const directoryHandle = await requestProjectDirectoryHandle()

  for (const directoryName of PROJECT_SUBDIRS) {
    await directoryHandle.getDirectoryHandle(directoryName, { create: true })
  }

  const now = getCurrentTimestampParts()
  const projectMeta: ProjectFileContent = {
    name: projectName,
    created_at: now.display,
    updated_at: now.display,
    save_mode: 'manual',
    version: '0.1.0',
  }
  await writeLocalJsonFile(directoryHandle, 'project.json', projectMeta)

  // 服务器只登记元数据（项目名 + 文件夹名标签），用于最近项目列表和聊天记录按项目隔离
  let registered: ProjectPayload | null = null
  try {
    registered = (await createProject(projectName, directoryHandle.name)).project
  } catch {
    ElMessage.warning('项目已在本地创建，但服务器登记失败，最近项目列表中可能看不到它')
  }
  if (typeof registered?.id === 'number') {
    projectMeta.id = registered.id
    await writeLocalJsonFile(directoryHandle, 'project.json', projectMeta)
  }

  ElMessage.success(`已创建项目：${projectName}`)
  emit('created', {
    id: registered?.id ?? null,
    name: projectName,
    projectPath: directoryHandle.name || '已选择项目文件夹',
    directoryHandle,
  })
}

async function saveCurrentAndCreate() {
  if (isCreating.value) return
  isCreating.value = true
  try {
    await ensureCurrentProjectSaved()
    await createNamedProject()
  } catch (error) {
    if (error instanceof Error && error.message !== USER_CANCELLED_DIRECTORY_PICKER) {
      ElMessage.error(error.message || '保存当前工程失败')
    }
  } finally {
    isCreating.value = false
  }
}

async function discardAndCreate() {
  if (isCreating.value) return
  isCreating.value = true
  try {
    await createNamedProject()
  } catch (error) {
    if (error instanceof Error && error.message !== USER_CANCELLED_DIRECTORY_PICKER) {
      ElMessage.error(error.message || '创建项目失败')
    }
  } finally {
    isCreating.value = false
  }
}
</script>

<style scoped>
/* 弹窗与按钮基元样式来自 workstation-base.css（跨组件共享） */
</style>
