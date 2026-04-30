import AskAIChip from './AskAIChip'

interface Props {
  icon: React.ReactNode
  title: string
  subtitle?: string
  aiPrompt?: string
}

export default function SectionHeader({ icon, title, subtitle, aiPrompt }: Props) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ color: '#f5222d' }}>{icon}</span>
      <span style={{ fontWeight: 600, fontSize: 15 }}>{title}</span>
      {subtitle && <span style={{ fontSize: 12, color: '#999' }}>{subtitle}</span>}
      {aiPrompt && <AskAIChip prompt={aiPrompt} />}
    </div>
  )
}
