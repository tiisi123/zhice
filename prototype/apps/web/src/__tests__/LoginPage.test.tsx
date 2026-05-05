import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', () => ({
  postApi: vi.fn(() => Promise.reject(new Error('no backend'))),
  fetchApi: vi.fn(() => Promise.reject(new Error('no backend'))),
}))

const { default: LoginPage } = await import('../pages/LoginPage')

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('renders the brand title', () => {
    renderPage()
    expect(screen.getByText('智策')).toBeInTheDocument()
  })

  it('renders the subtitle', () => {
    renderPage()
    expect(screen.getByText('AI 投研与策略中枢')).toBeInTheDocument()
  })

  it('shows the risk disclaimer', () => {
    renderPage()
    expect(screen.getByText(/投资有风险/)).toBeInTheDocument()
  })

  it('renders a card container', () => {
    const { container } = renderPage()
    expect(container.querySelector('.ant-card')).toBeTruthy()
  })
})
