import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getLastXDays } from '@/utils/dashboard'

describe('dashboard inclusive date presets', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 10, 16, 12))
  })
  afterEach(() => vi.useRealTimers())

  it('uses today for a single-day report', () => {
    expect(getLastXDays(1)).toBe('2026-11-16,2026-11-16')
  })
  it('includes exactly seven dates in the seven-day preset', () => {
    expect(getLastXDays(7)).toBe('2026-11-10,2026-11-16')
  })
  it('keeps the same inclusive length across a month boundary', () => {
    expect(getLastXDays(30)).toBe('2026-10-18,2026-11-16')
  })
})
