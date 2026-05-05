import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mocked(globalThis.fetch).mockResolvedValue(
  new Response(JSON.stringify({ data: [], source: 'test', data_status: 'mock', mock: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
)

const { default: StrategyWorkshopPage } = await import('../pages/StrategyWorkshopPage')

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/strategy-workshop']}>
      <StrategyWorkshopPage />
    </MemoryRouter>,
  )
}

describe('StrategyWorkshopPage', () => {
  it('renders the page heading', () => {
    renderPage()
    expect(screen.getByText('策略工坊')).toBeInTheDocument()
  })

  it('renders workshop tabs', () => {
    renderPage()
    expect(screen.getByRole('tab', { name: /推荐策略/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /打板回测/ })).toBeInTheDocument()
  })

  it('shows Monte Carlo disclaimer text', () => {
    const { container } = renderPage()
    expect(container.textContent).toContain('蒙特卡洛模拟')
  })
})
