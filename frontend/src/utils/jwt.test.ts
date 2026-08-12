// isTokenExpired 纯逻辑测试（F2）：过期判定、30 秒提前量、非法输入兜底
import { describe, expect, it } from 'vitest'
import { isTokenExpired } from '@/utils/jwt'

// 造一个只有 payload 有意义的假 JWT（前端不校验签名，header/signature 随意）
function fakeJwt(payload: Record<string, unknown>): string {
  const base64url = (obj: Record<string, unknown>) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${base64url({ alg: 'HS256' })}.${base64url(payload)}.fakesig`
}

const now = () => Math.floor(Date.now() / 1000)

describe('isTokenExpired', () => {
  it('未过期 token 返回 false', () => {
    expect(isTokenExpired(fakeJwt({ exp: now() + 3600 }))).toBe(false)
  })

  it('已过期 token 返回 true', () => {
    expect(isTokenExpired(fakeJwt({ exp: now() - 10 }))).toBe(true)
  })

  it('30 秒提前量：还剩 10 秒的 token 视为已过期', () => {
    expect(isTokenExpired(fakeJwt({ exp: now() + 10 }))).toBe(true)
  })

  it('null / 空串视为过期', () => {
    expect(isTokenExpired(null)).toBe(true)
    expect(isTokenExpired('')).toBe(true)
  })

  it('非 JWT 格式视为过期', () => {
    expect(isTokenExpired('not-a-jwt')).toBe(true)
    expect(isTokenExpired('a.b')).toBe(true)
  })

  it('payload 不是合法 base64/JSON 视为过期', () => {
    expect(isTokenExpired('aaa.!!!.ccc')).toBe(true)
  })

  it('无 exp 字段视为过期', () => {
    expect(isTokenExpired(fakeJwt({ sub: '1' }))).toBe(true)
  })

  it('中文 username 的 payload 能正确解码（base64url + UTF-8）', () => {
    // btoa 只能编 latin1，中文 payload 走 encodeURIComponent 路径构造
    const payload = JSON.stringify({ username: '张三', exp: now() + 3600 })
    const utf8b64 = btoa(
      encodeURIComponent(payload).replace(/%([0-9A-F]{2})/g, (_, h) =>
        String.fromCharCode(parseInt(h, 16)),
      ),
    )
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '')
    expect(isTokenExpired(`h.${utf8b64}.s`)).toBe(false)
  })
})
