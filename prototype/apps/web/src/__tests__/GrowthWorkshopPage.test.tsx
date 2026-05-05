import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/copilot', () => ({ askAI: vi.fn() }))

vi.mocked(globalThis.fetch).mockImplementation((url) => {
  const path = typeof url === 'string' ? url : url.toString()
  if (path.includes('/growth/macro')) {
    return Promise.resolve(new Response(JSON.stringify({ indicators: [{ name: 'PMI', value: 51, direction: 'up' }], source: 'test', data_status: 'mock', mock: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }
  if (path.includes('/growth/prosperity')) {
    return Promise.resolve(new Response(JSON.stringify({ industries: [], source: 'test', data_status: 'mock', mock: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }
  return Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } }))
})

const { default: GrowthWorkshopPage } = await import('../pages/GrowthWorkshopPage')

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/growth-workshop']}>
      <GrowthWorkshopPage />
    </MemoryRouter>,
  )
}

describe('GrowthWorkshopPage', () => {
  it('renders the page heading after data loads', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/成长景气/)).toBeInTheDocument()
    })
  })

  it('renders flow support indicator', async () => {
    const { container } = renderPage()
    await waitFor(() => {
      expect(container.textContent).toContain('流动性')
    })
  })
})
