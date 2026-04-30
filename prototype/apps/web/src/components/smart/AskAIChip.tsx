import { Tag } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import { askAI } from '../../api/copilot'

interface Props {
  prompt: string
  label?: string
}

export default function AskAIChip({ prompt, label = 'AI' }: Props) {
  return (
    <Tag
      icon={<RobotOutlined />}
      color="processing"
      style={{ cursor: 'pointer', fontSize: 11 }}
      onClick={() => askAI(prompt)}
    >
      {label}
    </Tag>
  )
}
