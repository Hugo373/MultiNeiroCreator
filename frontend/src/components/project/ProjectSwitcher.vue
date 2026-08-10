<template>
  <div ref="rootRef" class="topbar-combined">
    <div
      class="combined-left"
      :aria-expanded="isProjectOpen"
      @click.stop="toggleProjectPanel"
    >
      <span class="combined-label">{{ projectStore.tabLabel }}</span>
    </div>
    <div class="combined-divider" aria-hidden="true"></div>
    <div
      class="combined-right"
      :aria-expanded="isSearchOpen"
      @click.stop="toggleSearchPanel"
    >
      <span class="combined-right-text">搜索</span>
      <span class="search-signal" :class="{ active: isSearchOpen }" aria-hidden="true"></span>
    </div>

    <Transition name="panel-float">
      <div v-if="isProjectOpen" class="topbar-panel project-panel">
        <div class="project-switcher-group">
          <button class="project-switcher-option" type="button" @click="emitAction('create')">
            <div class="project-option-title">新建项目</div>
            <div class="project-option-meta">创建一个新的工程文件，并进入新的工作站界面。</div>
          </button>
          <button class="project-switcher-option" type="button" @click="emitAction('open-picker')">
            <div class="project-option-title">选择项目打开</div>
            <div class="project-option-meta">从本地工程列表中选择一个已有项目继续创作。</div>
          </button>
        </div>

        <div v-if="showRecentProjectsSection" class="project-switcher-group-label">最近打开</div>
        <div v-if="showRecentProjectsSection" class="project-history-list">
          <button
            v-for="item in displayedRecentProjects"
            :key="item.id"
            class="project-switcher-option"
            type="button"
            @click="handleOpenRecent(item)"
          >
            <div class="project-option-title">{{ item.title }}</div>
            <div class="project-option-meta">{{ item.meta }}</div>
          </button>
          <div v-if="showRecentProjectsEllipsis" class="project-history-ellipsis">...</div>
        </div>
      </div>
    </Transition>

    <Transition name="panel-float">
      <div v-if="isSearchOpen" class="topbar-panel search-panel">
        <div class="search-panel-title">{{ searchPanelTitle }}</div>
        <input
          v-model="searchQuery"
          type="text"
          placeholder=""
          @focus="openSearchPanel"
          @click.stop="openSearchPanel"
        />
        <div class="search-result-list">
          <button
            v-for="item in filteredSearchResults"
            :key="`${item.title}-${item.meta}`"
            class="search-result-item"
            type="button"
          >
            <div>{{ item.title }}</div>
            <div class="search-result-meta">{{ item.meta }}</div>
          </button>
        </div>
        <div v-if="showSearchEllipsis" class="search-result-ellipsis">...</div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
// 顶部栏项目切换 + 全局搜索面板（D1 拆分第 5 步，todo §8.4）。
// 项目动作（新建/打开/最近项目）通过事件上抛，由布局层执行流程。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useProjectStore, type RecentProjectItem } from '@/stores/project'

interface SearchItem {
  title: string
  meta: string
}

const emit = defineEmits<{
  (e: 'create'): void
  (e: 'open-picker'): void
  (e: 'open-recent', item: RecentProjectItem): void
}>()

const projectStore = useProjectStore()

const rootRef = ref<HTMLElement | null>(null)
const isProjectOpen = ref(false)
const isSearchOpen = ref(false)
const searchQuery = ref('')

const searchIndex: SearchItem[] = [
  { title: '选择项目', meta: '顶部栏 · 项目切换' },
  { title: '搜索', meta: '顶部栏 · 全局检索入口' },
  { title: '工具', meta: '左侧栏 · Creative Module Library' },
  { title: '添加工具', meta: '左侧栏 · 工具模块操作' },
  { title: 'Composer Agent', meta: '左侧栏 · 创作模块' },
  { title: 'Lyrics Agent', meta: '左侧栏 · 创作模块' },
  { title: 'Visual Agent', meta: '左侧栏 · 创作模块' },
  { title: '创作区', meta: '中间区域 · 工作区' },
  { title: 'Neyria', meta: '右侧栏 · AI 助手面板' },
  { title: '上传文件', meta: '右下输入区 · 功能按钮' },
  { title: '切换模型', meta: '右下输入区 · Auto 按钮' },
]

const filteredSearchResults = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) return []

  return searchIndex
    .filter(item => `${item.title} ${item.meta}`.toLowerCase().includes(keyword))
    .slice(0, 5)
})

const searchPanelTitle = computed(() => {
  if (!searchQuery.value.trim()) return '未搜索到相关内容'
  return filteredSearchResults.value.length ? '搜索到以下相关内容' : '未搜索到相关内容'
})

const showSearchEllipsis = computed(
  () => !!searchQuery.value.trim() && filteredSearchResults.value.length > 0,
)
const displayedRecentProjects = computed(() => projectStore.recentProjects.slice(0, 3))
const showRecentProjectsSection = computed(() => projectStore.recentProjects.length > 0)
const showRecentProjectsEllipsis = computed(() => projectStore.recentProjects.length > 3)

async function toggleProjectPanel() {
  const nextOpen = !isProjectOpen.value
  isProjectOpen.value = nextOpen
  isSearchOpen.value = false

  if (nextOpen) {
    await projectStore.loadRecentProjects()
  }
}

function toggleSearchPanel() {
  isSearchOpen.value = !isSearchOpen.value
  isProjectOpen.value = false
}

function openSearchPanel() {
  isSearchOpen.value = true
  isProjectOpen.value = false
}

function closePanels() {
  isProjectOpen.value = false
  isSearchOpen.value = false
}

function emitAction(action: 'create' | 'open-picker') {
  closePanels()
  if (action === 'create') {
    emit('create')
  } else {
    emit('open-picker')
  }
}

function handleOpenRecent(item: RecentProjectItem) {
  closePanels()
  emit('open-recent', item)
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target as Node | null
  if (rootRef.value && target && !rootRef.value.contains(target)) {
    closePanels()
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
.topbar-combined {
  height: 32px;
  position: relative;
  width: 463px;
  display: flex;
  align-items: center;
  padding: 0 10px;
  color: var(--text-secondary);
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.015);
}

.combined-label {
  color: var(--text-secondary);
  white-space: nowrap;
  transition: color 180ms ease, opacity 180ms ease;
}

.combined-left,
.combined-right {
  height: 100%;
  display: inline-flex;
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.combined-left {
  flex: 1;
  justify-content: flex-start;
  padding: 0 6px;
}

.combined-divider {
  width: 1px;
  height: 16px;
  background: rgba(255, 255, 255, 0.14);
  margin: 0 10px 0 6px;
}

.combined-right {
  justify-content: flex-end;
  min-width: 72px;
  padding-right: 6px;
  gap: 6px;
}

.combined-right-text {
  color: var(--text-secondary);
  transition: color 180ms ease, opacity 180ms ease;
}

.combined-left:hover {
  transform: translateY(-1px);
  filter: none;
}

.combined-left:hover .combined-label,
.combined-right:hover .combined-right-text {
  color: var(--text-primary);
}

.combined-left:active {
  transform: scale(0.992);
  transition-duration: 90ms;
}

.search-signal {
  width: 1px;
  height: 12px;
  background: rgba(230, 230, 230, 0.12);
  opacity: 0;
  border-radius: 999px;
  transform: scaleY(0.7);
}

.search-signal.active {
  opacity: 1;
  animation: search-blink 1s steps(2, end) infinite;
}

@keyframes search-blink {
  0%,
  45% {
    opacity: 0.12;
  }
  46%,
  100% {
    opacity: 0.92;
  }
}

.topbar-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  width: 100%;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  background: rgba(16, 16, 16, 0.94);
  backdrop-filter: blur(14px);
  z-index: 30;
  display: flex;
}

.project-switcher-group,
.project-history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.project-switcher-group-label {
  padding: 2px 10px 0;
  color: #6f6f6f;
  font-size: 12px;
  letter-spacing: 0.02em;
}

.project-switcher-option,
.search-result-item {
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: 16px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.project-option-title {
  color: inherit;
}

.project-option-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #6f6f6f;
  width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.project-history-ellipsis {
  padding: 2px 0 0;
  color: #6f6f6f;
  text-align: center;
  letter-spacing: 2px;
}

.search-panel-title {
  color: var(--text-primary);
  font-size: 13px;
}

.search-panel input {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  padding: 8px 10px;
  outline: none;
}

.search-result-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.search-result-item:hover,
.project-switcher-option:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.search-result-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #6f6f6f;
}

.search-result-ellipsis {
  color: var(--text-secondary);
  text-align: center;
  letter-spacing: 2px;
}
</style>
