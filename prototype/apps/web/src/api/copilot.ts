/**
 * 全局 AI Copilot 触发：打开抽屉并预填提示词，自动切到对话 Tab。
 * 用法：askAI('为什么今天机器人题材表现强势？')
 */
export function askAI(prompt: string): void {
  window.dispatchEvent(
    new CustomEvent('zhice:ai-ask', { detail: { prompt } })
  )
}
