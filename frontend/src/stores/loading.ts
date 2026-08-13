// 全局过渡覆盖层状态：调用方只调 show/hide/setProgress，不与路由耦合。
// hide() 保证最低展示时长（默认 1s）；setProgress > 0 后以真实进度为准，否则用内置 rAF 动画。
import { defineStore } from 'pinia'

export type LoadingMode = 'login' | 'register' | 'auto' | 'workstation'

const DEFAULTS: Record<LoadingMode, string> = {
  login: 'Preparing your workspace',
  register: 'Provisioning your studio',
  auto: 'Resuming your session',
  workstation: 'Resuming your session',
}

const DEFAULT_MIN_DURATION = 1000

// 延时句柄不放 state，避免序列化问题
let pendingHideTimer: ReturnType<typeof setTimeout> | null = null

export const useLoadingStore = defineStore('loading', {
  state: () => ({
    visible: false,
    /** 外部推动的真实进度；0 表示无真实进度 */
    realProgress: 0,
    shownAt: null as number | null,
    minDuration: DEFAULT_MIN_DURATION,
    mode: 'auto' as LoadingMode,
    label: 'Preparing your workspace',
  }),
  actions: {
    show(mode: LoadingMode = 'auto', options?: { minDuration?: number; label?: string }) {
      if (pendingHideTimer) {
        clearTimeout(pendingHideTimer)
        pendingHideTimer = null
      }
      this.visible = true
      this.shownAt = Date.now()
      this.realProgress = 0
      this.mode = mode
      this.label = options?.label || DEFAULTS[mode]
      this.minDuration =
        options?.minDuration != null ? Math.max(0, options.minDuration) : DEFAULT_MIN_DURATION
    },

    setProgress(p: number) {
      const v = Math.max(0, Math.min(100, Number(p) || 0))
      this.realProgress = v
    },

    setLabel(label: string) {
      if (label) this.label = label
    },

    setMinDuration(ms: number) {
      this.minDuration = Math.max(0, Number(ms) || 0)
    },

    // 未满最低展示时长时延后隐藏，其余立即隐藏
    hide() {
      if (!this.visible) {
        // 清掉挂起的延时，避免影响下次 show
        if (pendingHideTimer) {
          clearTimeout(pendingHideTimer)
          pendingHideTimer = null
        }
        return
      }
      if (this.shownAt == null) {
        this.visible = false
        this.realProgress = 0
        return
      }
      const elapsed = Date.now() - this.shownAt
      const remaining = Math.max(0, this.minDuration - elapsed)
      if (remaining === 0) {
        this.visible = false
        this.shownAt = null
        this.realProgress = 0
      } else {
        if (pendingHideTimer) {
          clearTimeout(pendingHideTimer)
        }
        pendingHideTimer = setTimeout(() => {
          pendingHideTimer = null
          this.visible = false
          this.shownAt = null
          this.realProgress = 0
        }, remaining)
      }
    },
  },
})
