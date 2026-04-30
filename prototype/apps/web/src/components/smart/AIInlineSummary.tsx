import { useEffect, useState } from 'react'
import { Skeleton } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import { fetchApi } from '../../api/client'

interface Props {
  endpoint: string
  params?: Record<string, string>
  field?: string
  fallback?: React.ReactNode
}

export default function AIInlineSummary({ endpoint, params, field = 'headline', fallback }: Props) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    fetchApi<Record<string, any>>(`${endpoint}${qs}`)
      .then(r => setText(String(r[field] || '') ))
      .catch(() => setText(''))
      .finally(() => setLoading(false))
  }, [endpoint, JSON.stringify(params), field])

  if (loading) {
    return (
      <div style={{
        background: 'linear-gradient(135deg,#141414,#262626)', borderRadius: 10,
        padding: '14px 20px', marginBottom: 16,
      }}>
        <Skeleton.Input active style={{ width: '80%', height: 20 }} />
      </div>
    )
  }
  if (!text) return fallback ? <>{fallback}</> : null
  return (
    <div style={{
      background: 'linear-gradient(135deg,#141414,#262626)', borderRadius: 10,
      padding: '14px 20px', marginBottom: 16, color: '#fff',
    }}>
      <RobotOutlined style={{ opacity: 0.5, marginRight: 8 }} />
      <span style={{ fontSize: 13, opacity: 0.5, marginRight: 8 }}>AI 速报</span>
      <span style={{ fontSize: 15, fontWeight: 600 }}>{text}</span>
    </div>
  )
}
