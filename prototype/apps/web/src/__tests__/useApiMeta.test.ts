import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { extractErrorMeta, extractMeta } from '../api/useApiMeta'

describe('useApiMeta helpers', () => {
  it('keeps auth failures distinct from empty business data', () => {
    const meta = extractErrorMeta(new ApiError('未登录或令牌失效', 401), '热股')

    expect(meta).toMatchObject({
      name: '热股',
      data_status: 'error',
      source: 'auth',
      mock: false,
      message: '未登录或令牌失效',
    })
  })

  it('still maps missing contract fields to empty unknown for contract drift', () => {
    expect(extractMeta({}, '漂移接口')).toMatchObject({
      name: '漂移接口',
      data_status: 'empty',
      source: 'unknown',
      mock: false,
    })
  })
})
