import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Radio, Button, Space, Typography, message, Steps, Tag, Alert } from 'antd'
import { fetchApi, postApi } from '../api/client'
import { setUser, getUser } from '../api/auth'
import type { AnyData } from '../api/types'

const { Title, Paragraph } = Typography

interface Question {
  id: string
  text: string
  options: { value: string; label: string }[]
}

const STYLE_LABEL: Record<string, string> = {
  short: '短线/打板',
  hot: '热点/轮动',
  growth: '成长/景气',
  value: '价值/基本面',
}

export default function StyleOnboardingPage() {
  const navigate = useNavigate()
  const [questions, setQuestions] = useState<Question[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [step, setStep] = useState(0)
  const [result, setResult] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    void fetchApi<{ questions: Question[] }>('/style/questions').then((r) => setQuestions(r.questions))
  }, [])

  if (questions.length === 0) return <Card loading />

  const q = questions[step]
  const total = questions.length
  const done = Object.keys(answers).length === total

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const r = await postApi<{ style: string }>('/style/submit', { answers })
      setResult(r.style)
      const u = getUser()
      if (u) setUser({ ...u, style: r.style as AnyData })
      message.success(`识别为：${STYLE_LABEL[r.style] || r.style}`)
    } catch (e) {
      message.error((e as Error)?.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (result) {
    return (
      <Card>
        <Alert
          type="success"
          showIcon
          message={
            <span>
              您的投资风格为：<Tag color="blue" style={{ fontSize: 16, padding: '2px 10px' }}>{STYLE_LABEL[result] || result}</Tag>
            </span>
          }
          description="我们会根据风格优化推荐内容、策略模板与 AI Copilot 提示。"
          style={{ marginBottom: 24 }}
        />
        <Space>
          <Button type="primary" onClick={() => navigate('/recommend')}>查看推荐策略</Button>
          <Button onClick={() => navigate('/replay')}>进入工作台</Button>
          <Button type="link" onClick={() => { setResult(null); setStep(0); setAnswers({}) }}>重新测试</Button>
        </Space>
      </Card>
    )
  }

  return (
    <Card>
      <Title level={3}>投资风格测试</Title>
      <Paragraph type="secondary">5 道题，30 秒，识别你的主风格。</Paragraph>
      <Steps current={step} size="small" style={{ margin: '24px 0' }}
        items={questions.map((_, i) => ({ title: `Q${i + 1}` }))}
      />
      <Card type="inner" title={q.text}>
        <Radio.Group
          value={answers[q.id]}
          onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          {q.options.map((opt) => (
            <Radio key={opt.value} value={opt.value}>{opt.label}</Radio>
          ))}
        </Radio.Group>
      </Card>
      <Space style={{ marginTop: 24 }}>
        <Button disabled={step === 0} onClick={() => setStep(step - 1)}>上一题</Button>
        {step < total - 1 && (
          <Button type="primary" disabled={!answers[q.id]} onClick={() => setStep(step + 1)}>
            下一题
          </Button>
        )}
        {step === total - 1 && (
          <Button type="primary" disabled={!done} loading={submitting} onClick={handleSubmit}>
            提交
          </Button>
        )}
      </Space>
    </Card>
  )
}
