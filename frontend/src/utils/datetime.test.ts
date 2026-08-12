// 日期格式化纯函数测试（F2：todo §4.3 "日期"纯逻辑）
import { describe, expect, it } from 'vitest'
import { formatProjectTime, getCurrentTimestampParts } from '@/utils/datetime'

describe('getCurrentTimestampParts', () => {
  it('display 与 file 两种格式且零填充', () => {
    const parts = getCurrentTimestampParts(new Date(2026, 0, 5, 9, 3, 7)) // 2026-01-05 09:03:07
    expect(parts.display).toBe('2026-01-05 09:03:07')
    expect(parts.file).toBe('20260105_090307')
  })
})

describe('formatProjectTime', () => {
  it('服务端 "YYYY-MM-DD HH:mm:ss" 转 "MM-DD HH:mm"', () => {
    expect(formatProjectTime('2026-08-12 14:30:00')).toBe('08-12 14:30')
  })

  it('ISO 格式也能解析', () => {
    expect(formatProjectTime('2026-08-12T14:30:00')).toBe('08-12 14:30')
  })

  it('解析失败原样返回，不抛异常', () => {
    expect(formatProjectTime('not a date')).toBe('not a date')
    expect(formatProjectTime('')).toBe('')
  })
})
