import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

const { default: EventChainPage } = await import('../pages/EventChainPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <EventChainPage />
    </MemoryRouter>,
  )
}

describe('EventChainPage', () => {
  it('renders the page title', () => {
    renderPage()
    expect(screen.getByText('事件影响链')).toBeInTheDocument()
  })

  it('renders the search input', () => {
    renderPage()
    expect(screen.getByPlaceholderText(/输入关键词搜索事件链/)).toBeInTheDocument()
  })

  it('shows empty state before search', () => {
    renderPage()
    expect(screen.getByText('输入关键词搜索事件链')).toBeInTheDocument()
  })
})
