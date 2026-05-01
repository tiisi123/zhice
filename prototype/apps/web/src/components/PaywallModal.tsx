import { Modal, Typography, Space, Button } from 'antd'
import { CrownOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

const { Title, Paragraph } = Typography

interface Props {
  open: boolean
  onClose: () => void
}

export default function PaywallModal({ open, onClose }: Props) {
  const navigate = useNavigate()

  return (
    <Modal open={open} onCancel={onClose} footer={null} centered width={400}>
      <Space direction="vertical" size="middle" style={{ width: '100%', textAlign: 'center', padding: '16px 0' }}>
        <CrownOutlined style={{ fontSize: 48, color: '#faad14' }} />
        <Title level={4} style={{ margin: 0 }}>升级会员</Title>
        <Paragraph type="secondary">
          解锁完整内容、AI 分析、策略回测等高级功能
        </Paragraph>
        <Space>
          <Button
            type="primary"
            onClick={() => { void navigate('/account/membership'); onClose() }}
          >
            查看套餐
          </Button>
          <Button onClick={onClose}>稍后再说</Button>
        </Space>
      </Space>
    </Modal>
  )
}
