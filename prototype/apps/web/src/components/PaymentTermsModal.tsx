import { useState } from 'react'
import { Modal, Typography, Checkbox, Button } from 'antd'
import { ExclamationCircleOutlined } from '@ant-design/icons'

const { Title, Paragraph } = Typography

interface Props {
  open: boolean
  onAccept: () => void
  onClose: () => void
}

const PAYMENT_TEXT =
  '我确认：已阅读并理解《风险提示》，本人理解平台内容不构成投资建议，付费内容仅为信息服务。'

export default function PaymentTermsModal({ open, onAccept, onClose }: Props) {
  const [checked, setChecked] = useState(false)

  return (
    <Modal
      open={open}
      centered
      width={480}
      closable
      onCancel={onClose}
      footer={null}
    >
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <ExclamationCircleOutlined style={{ fontSize: 36, color: '#faad14' }} />
        <Title level={4} style={{ margin: '12px 0 0' }}>付费服务确认</Title>
      </div>
      <div style={{
        background: '#fffbe6',
        border: '1px solid #ffe58f',
        borderRadius: 6,
        padding: '16px',
        marginBottom: 20,
      }}>
        <Paragraph style={{ margin: 0, lineHeight: 1.8, color: '#874d00' }}>
          {PAYMENT_TEXT}
        </Paragraph>
      </div>
      <div style={{ marginBottom: 20 }}>
        <Checkbox checked={checked} onChange={(e) => setChecked(e.target.checked)}>
          我已阅读并同意以上条款
        </Checkbox>
      </div>
      <Button type="primary" block size="large" disabled={!checked} onClick={onAccept}>
        确认并继续
      </Button>
    </Modal>
  )
}
