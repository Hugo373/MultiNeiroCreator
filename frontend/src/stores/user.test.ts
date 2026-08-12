// user store 测试（F2 第一批清单：登录 401 只清用户态，不连坐其他 localStorage 数据）
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { TOKEN_KEY, USERNAME_KEY } from '@/constants'
import { useUserStore } from '@/stores/user'

describe('useUserStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('setUser 同步写入 state 与 localStorage', () => {
    const store = useUserStore()
    store.setUser('tok123', 'alice')
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem(TOKEN_KEY)).toBe('tok123')
    expect(localStorage.getItem(USERNAME_KEY)).toBe('alice')
  })

  it('logout 只清用户态两个 key，不连坐其他数据（B2 回归）', () => {
    localStorage.setItem('draft_message', '写到一半的内容')
    localStorage.setItem('remember', '1')
    const store = useUserStore()
    store.setUser('tok123', 'alice')

    store.logout()

    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(USERNAME_KEY)).toBeNull()
    // 其他业务数据必须幸存——历史 bug 是 localStorage.clear() 全清
    expect(localStorage.getItem('draft_message')).toBe('写到一半的内容')
    expect(localStorage.getItem('remember')).toBe('1')
  })

  it('初始化从 localStorage 恢复登录态', () => {
    localStorage.setItem(TOKEN_KEY, 'persisted-token')
    localStorage.setItem(USERNAME_KEY, 'bob')
    setActivePinia(createPinia())
    const store = useUserStore()
    expect(store.token).toBe('persisted-token')
    expect(store.username).toBe('bob')
  })
})
