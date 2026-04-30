import { postApi } from './client'

export function track(event: string, page?: string, props?: Record<string, unknown>) {
  // fire-and-forget
  postApi('/events/track', { event, page, props }).catch(() => {})
}
