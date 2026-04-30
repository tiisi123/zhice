import { Alert } from 'antd'
import { ExclamationCircleOutlined } from '@ant-design/icons'

/**
 * AI 风险免责声明 · 统一合规组件（PRD 合规要求）
 * - 所有由 AI 生成的策略 / 摘要 / 推荐 / 预测内容旁，均需展示
 * - 三种尺寸：inline（小字脚注）、compact（卡片底部一行）、full（完整 Alert）
 */

const TEXT_FULL = 'AI 生成内容仅供参考，基于历史数据与模型推演，不构成投资建议。市场有风险，投资需谨慎，请独立判断并自行承担风险。'
const TEXT_SHORT = 'AI 内容仅供参考，不构成投资建议；市场有风险，投资需谨慎。'

interface Props {
  variant?: 'inline' | 'compact' | 'full'
  style?: React.CSSProperties
}

export default function AIDisclaimer({ variant = 'inline', style }: Props) {
  if (variant === 'full') {
    return (
      <Alert
        type="warning"
        showIcon
        icon={<ExclamationCircleOutlined />}
        message="风险提示"
        description={TEXT_FULL}
        style={{ marginTop: 12, ...style }}
      />
    )
  }
  if (variant === 'compact') {
    return (
      <div
        style={{
          marginTop: 10,
          padding: '4px 10px',
          background: '#fffbe6',
          border: '1px solid #ffe58f',
          borderRadius: 4,
          fontSize: 11,
          color: '#874d00',
          ...style,
        }}
      >
        <ExclamationCircleOutlined style={{ marginRight: 6 }} />
        {TEXT_SHORT}
      </div>
    )
  }
  // inline
  return (
    <div style={{ fontSize: 11, color: '#999', textAlign: 'center', marginTop: 8, ...style }}>
      {TEXT_SHORT}
    </div>
  )
}
