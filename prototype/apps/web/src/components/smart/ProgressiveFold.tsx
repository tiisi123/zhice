import { useState } from 'react'
import { Button } from 'antd'
import { DownOutlined, UpOutlined } from '@ant-design/icons'

interface Props {
  id: string
  label?: string
  count?: number
  defaultOpen?: boolean
  children: React.ReactNode
}

export default function ProgressiveFold({ id, label = '展开详情', count, defaultOpen = false, children }: Props) {
  const storageKey = `zhice:fold:${id}`
  const [open, setOpen] = useState(() => {
    try { const v = localStorage.getItem(storageKey); return v !== null ? v === '1' : defaultOpen } catch { return defaultOpen }
  })

  const toggle = () => {
    const next = !open
    setOpen(next)
    try { localStorage.setItem(storageKey, next ? '1' : '0') } catch { /* noop */ }
  }

  return (
    <div>
      {open && <div style={{ marginBottom: 8 }}>{children}</div>}
      <Button
        type="link" size="small"
        icon={open ? <UpOutlined /> : <DownOutlined />}
        onClick={toggle}
        style={{ padding: 0, fontSize: 12, color: '#999' }}
      >
        {open ? '收起' : label}{count != null && !open ? ` (${count})` : ''}
      </Button>
    </div>
  )
}
