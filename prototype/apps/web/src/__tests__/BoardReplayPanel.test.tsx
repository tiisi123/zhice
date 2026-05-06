import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const { default: BoardReplayPanel } = await import('../components/BoardReplayPanel')

describe('BoardReplayPanel', () => {
  it('renders change_rate as percentage points without multiplying by 100', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: {
          first_board: [{
            stock_code: '000620',
            stock_name: '盈新发展',
            change_rate: 10.0,
            board_count: 1,
            limit_time: '09:25:00',
            seal_amount: 1000000,
            sectors: ['测试题材'],
          }],
          consecutive: [],
          broken: [],
        },
        source: 'kpl',
        data_status: 'real',
        mock: false,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<BoardReplayPanel date="2026-05-06" />)

    await waitFor(() => {
      expect(screen.getByText('10.00%')).toBeInTheDocument()
    })
    expect(screen.queryByText('1000.00%')).not.toBeInTheDocument()
  })
})
