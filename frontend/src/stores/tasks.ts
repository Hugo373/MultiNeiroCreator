import { computed, onScopeDispose, ref, watch, type Ref, type WatchHandle } from 'vue'
import { defineStore } from 'pinia'
import {
  cancelAgentJob,
  getAgentDocuments,
  getAgentJobs,
  retryAgentJob,
  type AgentDocument,
  type JobItem,
} from '@/serve/agent'

export const useTaskStore = defineStore('tasks', () => {
  const documents = ref<AgentDocument[]>([])
  const jobs = ref<JobItem[]>([])
  const isLoading = ref(false)
  const error = ref('')
  let pollingTimer: number | null = null
  let stopProjectWatch: WatchHandle | null = null
  let requestToken = 0

  const activeJobs = computed(() =>
    jobs.value.filter((job) => job.status === 'queued' || job.status === 'running'),
  )
  const hasActiveTasks = computed(
    () =>
      activeJobs.value.length > 0 || documents.value.some((item) => item.status === 'processing'),
  )

  async function load(projectId: number | null | undefined) {
    const token = ++requestToken
    if (projectId == null) {
      documents.value = []
      jobs.value = []
      return
    }
    isLoading.value = true
    error.value = ''
    try {
      const [nextDocuments, nextJobs] = await Promise.all([
        getAgentDocuments(projectId),
        getAgentJobs(projectId),
      ])
      if (token !== requestToken) return
      documents.value = nextDocuments
      jobs.value = nextJobs
    } catch (cause) {
      if (token !== requestToken) return
      error.value = cause instanceof Error ? cause.message : '任务状态加载失败'
    } finally {
      if (token === requestToken) isLoading.value = false
    }
  }

  function startPolling(projectId: Ref<number | null>) {
    stopPolling()
    void load(projectId.value)
    stopProjectWatch?.()
    stopProjectWatch = watch(projectId, (next) => void load(next))
    pollingTimer = window.setInterval(() => {
      if (hasActiveTasks.value) void load(projectId.value)
    }, 1500)
  }

  function stopPolling() {
    if (stopProjectWatch !== null) {
      stopProjectWatch()
      stopProjectWatch = null
    }
    if (pollingTimer !== null) {
      window.clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  async function cancel(jobId: string) {
    await cancelAgentJob(jobId)
    await load(jobs.value.find((job) => job.id === jobId)?.project_id)
  }

  async function retry(jobId: string) {
    await retryAgentJob(jobId)
    await load(jobs.value.find((job) => job.id === jobId)?.project_id)
  }

  onScopeDispose(stopPolling)

  return {
    documents,
    jobs,
    isLoading,
    error,
    activeJobs,
    hasActiveTasks,
    load,
    startPolling,
    stopPolling,
    cancel,
    retry,
  }
})
