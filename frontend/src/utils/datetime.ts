/** 时间格式化纯函数（从 WorkstationLayout 拆出，D1） */

export function getCurrentTimestampParts(date = new Date()) {
  const year = String(date.getFullYear())
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')

  return {
    display: `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`,
    file: `${year}${month}${day}_${hours}${minutes}${seconds}`,
  }
}

/** 服务端时间 -> "MM-DD HH:mm"，解析失败原样返回 */
export function formatProjectTime(value: string): string {
  const parsed = new Date(value.replace(' ', 'T'))
  if (Number.isNaN(parsed.getTime())) return value

  const month = String(parsed.getMonth() + 1).padStart(2, '0')
  const date = String(parsed.getDate()).padStart(2, '0')
  const hours = String(parsed.getHours()).padStart(2, '0')
  const minutes = String(parsed.getMinutes()).padStart(2, '0')
  return `${month}-${date} ${hours}:${minutes}`
}
