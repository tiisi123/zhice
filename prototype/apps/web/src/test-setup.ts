import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  localStorage.clear()
})

globalThis.fetch = vi.fn(() =>
  Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })),
)

const noop = () => {}
const canvasCtx = {
  clearRect: noop, fillRect: noop, strokeRect: noop,
  fillText: noop, strokeText: noop, measureText: () => ({ width: 0 }),
  beginPath: noop, closePath: noop, moveTo: noop, lineTo: noop,
  arc: noop, arcTo: noop, bezierCurveTo: noop, quadraticCurveTo: noop, rect: noop, ellipse: noop,
  fill: noop, stroke: noop, clip: noop,
  save: noop, restore: noop, scale: noop, rotate: noop, translate: noop,
  transform: noop, setTransform: noop, resetTransform: noop,
  drawImage: noop, createLinearGradient: () => ({ addColorStop: noop }),
  createRadialGradient: () => ({ addColorStop: noop }),
  createPattern: () => null,
  getImageData: () => ({ data: new Uint8ClampedArray(0), width: 0, height: 0 }),
  putImageData: noop, createImageData: () => ({ data: new Uint8ClampedArray(0), width: 0, height: 0 }),
  setLineDash: noop, getLineDash: () => [],
  canvas: { width: 300, height: 150 },
}
HTMLCanvasElement.prototype.getContext = (() => canvasCtx) as never

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof globalThis.ResizeObserver

globalThis.matchMedia = ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => false,
})) as typeof globalThis.matchMedia
