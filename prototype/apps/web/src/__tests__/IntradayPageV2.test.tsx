import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/useMarketWS', () => ({
  useMarketWS: vi.fn(() => ({ data: null, status: 'closed' })),
}))

vi.mocked(globalThis.fetch).mockResolvedValue(
  new Response(JSON.stringify({ data: [], source: 'test', data_status: 'mock', mock: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
)

const { default: IntradayPageV2 } = await import('../pages/IntradayPageV2')

function renderPage() {
  return render(
    <MemoryRouter>
      <IntradayPageV2 />
    </MemoryRouter>,
  )
}

describe('IntradayPageV2', () => {
  it('renders without crashing', () => {
    const { container } = renderPage()
    expect(container.firstChild).toBeTruthy()
  })

  it('calls market APIs on mount', async () => {
    renderPage()
    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls
      expect(calls.length).toBeGreaterThan(0)
    })
  })
})
