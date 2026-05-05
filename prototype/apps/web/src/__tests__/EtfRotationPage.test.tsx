import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mocked(globalThis.fetch).mockResolvedValue(
  new Response(JSON.stringify({
    as_of: '2026-05-05', data_mode: 'mock', data_status: 'mock',
    source: 'test', mock: true, etfs: [], rotation_links: [],
    heatmap: [], trajectory: [],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
)

const { default: EtfRotationPage } = await import('../pages/EtfRotationPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <EtfRotationPage />
    </MemoryRouter>,
  )
}

describe('EtfRotationPage', () => {
  it('renders without crashing', () => {
    const { container } = renderPage()
    expect(container.firstChild).toBeTruthy()
  })

  it('fetches dashboard data on mount', async () => {
    renderPage()
    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls
      expect(calls.some(([url]) => typeof url === 'string' && url.includes('/etf/rotation/dashboard'))).toBe(true)
    })
  })
})
