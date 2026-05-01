import { useState } from 'react'
import { Modal, Typography, Checkbox, Button } from 'antd'
import { ExclamationCircleOutlined } from '@ant-design/icons'

const { Title, Paragraph } = Typography

interface Props {
  open: boolean
  onAccept: () => void
}

const RISK_TEXT =
  '本平台所有数据、分析及 AI 生成内容均基于历史数据与模型推演，仅供研究参考，不构成任何投资建议。' +
  '市场有风险，投资需谨慎。用户应独立判断并自行承担投资风险。' +
  '本平台不持有投资顾问牌照，不提供个性化投资咨询服务。'

export default function RegisterTermsModal({ open, onAccept }: Props) {
  const [checked, setChecked] = useState(false)

  return (
    <Modal
      open={open}
      centered
      width={520}
      closable={false}
      maskClosable={false}
      keyboard={false}
      footer={null}
    >
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <ExclamationCircleOutlined style={{ fontSize: 36, color: '#faad14' }} />
        <Title level={4} style={{ margin: '12px 0 0' }}>风险提示</Title>
      </div>
      <div style={{
        background: '#fffbe6',
        border: '1px solid #ffe58f',
        borderRadius: 6,
        padding: '16px',
        marginBottom: 20,
        maxHeight: 200,
        overflowY: 'auto',
      }}>
        <Paragraph style={{ margin: 0, lineHeight: 1.8, color: '#874d00' }}>
          {RISK_TEXT}
        </Paragraph>
      </div>
      <div style={{ marginBottom: 20 }}>
        <Checkbox checked={checked} onChange={(e) => setChecked(e.target.checked)}>
          我已阅读并理解《风险提示》及平台免责条款
        </Checkbox>
      </div>
      <Button type="primary" block size="large" disabled={!checked} onClick={onAccept}>
        确认并继续注册
      </Button>
    </Modal>
  )
}
