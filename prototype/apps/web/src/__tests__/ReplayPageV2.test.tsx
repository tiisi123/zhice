import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/copilot', () => ({ askAI: vi.fn() }))

vi.mocked(globalThis.fetch).mockImplementation(() =>
  Promise.resolve(new Response(JSON.stringify({ data: [], source: 'test', data_status: 'mock', mock: true }), { status: 200, headers: { 'Content-Type': 'application/json' } })),
)

const { default: ReplayPageV2 } = await import('../pages/ReplayPageV2')

function renderPage() {
  return render(
    <MemoryRouter>
      <ReplayPageV2 />
    </MemoryRouter>,
  )
}

describe('ReplayPageV2', () => {
  it('renders without crashing', () => {
    const { container } = renderPage()
    expect(container.firstChild).toBeTruthy()
  })

  it('calls market summary API on mount', async () => {
    renderPage()
    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls
      expect(calls.some(([url]) => typeof url === 'string' && url.includes('/market/summary'))).toBe(true)
    })
  })

  it('calls multiple market endpoints', async () => {
    renderPage()
    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls
      expect(calls.length).toBeGreaterThanOrEqual(3)
    })
  })
})
