/**
 * 平滑打字机：SSE 的 token 是一簇一簇到达的（一个网络包常带十几个字），
 * 到多少上屏多少会呈现一顿一顿的跳字感。这里把到达文本先进缓冲，用
 * requestAnimationFrame 按帧吐出：基线每帧 1 字（约 60 字/秒）；缓冲积压时
 * 自适应加速（每帧吐 buffer/CATCH_UP_FRAMES，约 0.4 秒内追平），
 * 因此显示最多落后生成约 0.4 秒，永远不会越拉越远。
 */
export interface Typewriter {
  /** 收到一段流式文本，进缓冲排队上屏 */
  push(text: string): void
  /** 流已结束：等缓冲全部吐完后 resolve */
  finish(): Promise<void>
  /** 错误/中断：停止吐字并丢弃缓冲（调用方随后会整体改写内容） */
  cancel(): void
}

const CATCH_UP_FRAMES = 24

export function createTypewriter(apply: (text: string) => void): Typewriter {
  let buffer = ''
  let rafId: number | null = null
  let finished = false
  let resolveFinish: (() => void) | null = null

  function step() {
    rafId = null
    if (buffer) {
      const count = Math.max(1, Math.ceil(buffer.length / CATCH_UP_FRAMES))
      apply(buffer.slice(0, count))
      buffer = buffer.slice(count)
    }
    if (buffer) {
      rafId = requestAnimationFrame(step)
    } else if (finished) {
      resolveFinish?.()
      resolveFinish = null
    }
  }

  function schedule() {
    if (rafId === null) rafId = requestAnimationFrame(step)
  }

  return {
    push(text: string) {
      if (finished || !text) return
      buffer += text
      schedule()
    },
    finish() {
      finished = true
      if (!buffer && rafId === null) return Promise.resolve()
      return new Promise<void>((resolve) => {
        resolveFinish = resolve
        schedule()
      })
    },
    cancel() {
      finished = true
      buffer = ''
      if (rafId !== null) cancelAnimationFrame(rafId)
      rafId = null
      resolveFinish?.()
      resolveFinish = null
    },
  }
}
