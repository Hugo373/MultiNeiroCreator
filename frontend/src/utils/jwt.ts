// JWT 的前端本地解析（只读 payload，不做签名校验——签名真伪由后端把关，
// 前端解 exp 只是为了在请求发出前就感知过期，避免"点了半天才发现要重新登录"）。

interface JwtPayload {
  exp?: number
  [key: string]: unknown
}

function decodeJwtPayload(token: string): JwtPayload | null {
  const parts = token.split('.')
  if (parts.length !== 3) return null
  try {
    // JWT 用 base64url（-、_ 替代 +、/，去 padding），atob 前要还原
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map(char => '%' + ('00' + char.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    )
    return JSON.parse(json) as JwtPayload
  } catch {
    return null
  }
}

// 提前 30 秒判定过期：本地时钟偏差 + 请求在途时间的余量
const EXPIRY_SKEW_SECONDS = 30

/** token 缺失、格式非法、无 exp 或已过期时返回 true（一律按需要重新登录处理） */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true
  const payload = decodeJwtPayload(token)
  if (!payload || typeof payload.exp !== 'number') return true
  return payload.exp <= Date.now() / 1000 + EXPIRY_SKEW_SECONDS
}
