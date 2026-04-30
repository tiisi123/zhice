import { Alert } from 'antd'

interface Props {
  /** 页面/功能类型，决定提示内容 */
  kind?: 'ai' | 'backtest' | 'recommend' | 'forecast' | 'general'
  style?: React.CSSProperties
}

const TEXTS: Record<string, string> = {
  ai: 'AI 生成内容仅供研究参考，可能存在偏差或错误，不构成任何投资建议。',
  backtest: '回测结果基于历史数据模拟，过往业绩不代表未来表现。投资有风险，决策请独立判断。',
  recommend: '策略推荐根据用户风格匹配生成，不构成投资建议；请结合自身风险承受能力使用。',
  forecast: '预测/估值模型基于公开数据与假设，存在偏差与不确定性，仅供研究参考。',
  general: '本页面所有数据与分析仅供研究参考，不构成投资建议。',
}

export default function Disclaimer({ kind = 'general', style }: Props) {
  return (
    <Alert
      type="warning"
      showIcon
      banner
      message={TEXTS[kind] || TEXTS.general}
      style={{ marginBottom: 12, ...style }}
    />
  )
}
