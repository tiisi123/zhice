/**
 * DemoBadgePage — DataStatusBadge 4 态可手测 demo 页
 *
 * 路由：/dev/data-status-badge（仅 dev 模式注册，AuthGuard 之外）
 * 用途：S02 路由批量改造前先验证组件视觉与文案，业主 / S02 实现者可直接对照
 */

import { Card, Row, Col, Typography, Space } from 'antd'
import DataStatusBadge from '../components/DataStatusBadge'

const { Title, Paragraph, Text } = Typography

interface DemoCardProps {
  title: string
  scenario: string
  badge: React.ReactNode
}

function DemoCard({ title, scenario, badge }: DemoCardProps) {
  return (
    <Card
      size="small"
      title={
        <Space>
          <span>{title}</span>
          {badge}
        </Space>
      }
      style={{ minHeight: 140 }}
    >
      <Paragraph style={{ marginBottom: 8 }}>
        <Text type="secondary">场景：</Text>
        <Text>{scenario}</Text>
      </Paragraph>
      <Paragraph style={{ marginBottom: 0 }}>
        <Text type="secondary">徽标（无 source）：</Text>
      </Paragraph>
      <div style={{ marginTop: 4 }}>{badge}</div>
    </Card>
  )
}

export default function DemoBadgePage() {
  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={2}>DataStatusBadge — 4 态 + mock 覆盖演示</Title>
      <Paragraph type="secondary">
        本页面仅 dev 模式可见，用于 S02 数据契约改造前先行手测组件视觉与文案。
        每个 Card 上方为带 source 的 Tooltip 版本（鼠标悬停可见 "数据源: xxx"），下方为无 source 版本。
      </Paragraph>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={8}>
          <DemoCard
            title="real（实时数据）"
            scenario="接口返回 source=kpl, data_status=ok, mock=false"
            badge={<DataStatusBadge status="real" source="kpl" />}
          />
        </Col>

        <Col xs={24} sm={12} md={8}>
          <DemoCard
            title="fallback（降级数据）"
            scenario="主源 KPL 超时，已降级到 eastmoney（data_status=degraded）"
            badge={<DataStatusBadge status="fallback" source="eastmoney" />}
          />
        </Col>

        <Col xs={24} sm={12} md={8}>
          <DemoCard
            title="unavailable（数据源不可用）"
            scenario="所有数据源都失败（data_status=error），业主需排障"
            badge={<DataStatusBadge status="unavailable" source="kpl,eastmoney" />}
          />
        </Col>

        <Col xs={24} sm={12} md={8}>
          <DemoCard
            title="empty（暂无数据）"
            scenario="数据源响应正常但无内容（如非交易日 / 筛选条件无匹配）"
            badge={<DataStatusBadge status="empty" source="kpl" />}
          />
        </Col>

        <Col xs={24} sm={12} md={8}>
          <DemoCard
            title="mock=true（演示数据覆盖）"
            scenario="开发或演示态，mock=true 强制覆盖 status，颜色变 yellow / 文案变 '演示数据'"
            badge={<DataStatusBadge status="real" source="mock-fixture" mock />}
          />
        </Col>

        <Col xs={24} sm={12} md={8}>
          <DemoCard
            title="size=small（紧凑变体）"
            scenario="嵌入紧凑 KPI 卡片或表格表头时使用 small 字号"
            badge={<DataStatusBadge status="real" source="kpl" size="small" />}
          />
        </Col>
      </Row>
    </div>
  )
}
