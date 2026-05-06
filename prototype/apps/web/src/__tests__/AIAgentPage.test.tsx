import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mocked(globalThis.fetch).mockResolvedValue(
  new Response(JSON.stringify({ data: { advice: '' }, source: 'test', data_status: 'mock', mock: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
)

const { default: AIAgentPage } = await import('../pages/AIAgentPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <AIAgentPage />
    </MemoryRouter>,
  )
}

describe('AIAgentPage', () => {
  it('renders without crashing and contains tab content', () => {
    const { container } = renderPage()
    expect(container.textContent).toContain('打板')
    expect(container.textContent).toContain('ETF')
  })

  it('renders the generate-advice button', () => {
    renderPage()
    expect(screen.getAllByText('生成建议').length).toBeGreaterThan(0)
  })

  it('renders the form with style selector', () => {
    renderPage()
    expect(screen.getByText('交易风格')).toBeInTheDocument()
  })
})
