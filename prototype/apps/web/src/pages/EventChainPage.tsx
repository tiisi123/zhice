import { useState } from 'react'
import { Card, Col, Empty, Input, List, Row, Space, Spin, Tag, Typography } from 'antd'
import { ApartmentOutlined } from '@ant-design/icons'
import { fetchApi } from '../api/client'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'
import type { AnyData, DataStatus, EventChainData } from '../api/types'

const { Title, Paragraph, Text } = Typography
const { Search } = Input

const SEGMENT_CONFIG = [
  { key: 'upstream' as const, label: '上游', color: '#1677ff' },
  { key: 'midstream' as const, label: '中游', color: '#fa8c16' },
  { key: 'downstream' as const, label: '下游', color: '#52c41a' },
]

export default function EventChainPage() {
  const [keyword, setKeyword] = useState('')
  const [data, setData] = useState<EventChainData | null>(null)
  const [raw, setRaw] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = (value: string) => {
    const kw = value.trim()
    if (!kw) return
    setKeyword(kw)
    setLoading(true)
    setSearched(true)
    fetchApi<AnyData>(`/analysis/event-chain?keyword=${encodeURIComponent(kw)}`)
      .then((res) => {
        setRaw(res)
        setData(res?.data ?? null)
      })
      .catch(() => {
        setRaw(null)
        setData(null)
      })
      .finally(() => setLoading(false))
  }

  const meta = extractMeta(raw, '事件链')

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        <ApartmentOutlined style={{ color: '#1677ff', marginRight: 8 }} />
        事件影响链
      </Title>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap style={{ width: '100%' }}>
          <Search
            placeholder="输入关键词搜索事件链 (如: 芯片、新能源)"
            allowClear
            enterButton="搜索"
            size="middle"
            style={{ width: 400 }}
            onSearch={handleSearch}
            loading={loading}
          />
          {searched && (
            <DataStatusBadge
              status={meta.data_status as DataStatus}
              source={meta.source}
              mock={meta.mock}
              size="small"
            />
          )}
        </Space>
      </Card>

      {loading ? (
        <Card><Spin /></Card>
      ) : !searched ? (
        <Card>
          <Empty description="输入关键词搜索事件链" />
        </Card>
      ) : !data ? (
        <Card>
          <Empty description={`未找到「${keyword}」相关的事件链`} />
        </Card>
      ) : (
        <>
          <Card
            size="small"
            title={
              <Space>
                <Tag color="blue">{data.chain_name}</Tag>
                <Text type="secondary" style={{ fontSize: 12 }}>关键词: {data.keyword}</Text>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Row gutter={[16, 16]}>
              {SEGMENT_CONFIG.map(({ key, label, color }) => {
                const items = data.matched_chain[key]
                return (
                  <Col xs={24} md={8} key={key}>
                    <Card
                      size="small"
                      title={<Tag color={color}>{label}</Tag>}
                      style={{ height: '100%' }}
                    >
                      {items.length > 0 ? (
                        <List
                          size="small"
                          dataSource={items}
                          renderItem={(item) => (
                            <List.Item style={{ padding: '4px 0' }}>
                              <Text>{item}</Text>
                            </List.Item>
                          )}
                        />
                      ) : (
                        <Text type="secondary">暂无</Text>
                      )}
                    </Card>
                  </Col>
                )
              })}
            </Row>
          </Card>

          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={24} md={12}>
              <Card size="small" title="传导逻辑">
                <Paragraph style={{ marginBottom: 0 }}>
                  {data.transmission_logic || '暂无传导逻辑描述'}
                </Paragraph>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card size="small" title="传导时滞">
                <Paragraph style={{ marginBottom: 0 }}>
                  {data.transmission_lag || '暂无传导时滞描述'}
                </Paragraph>
              </Card>
            </Col>
          </Row>

          {data.llm_analysis && (
            <Card size="small" title="AI 分析" style={{ marginBottom: 16 }}>
              <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                {data.llm_analysis}
              </Paragraph>
            </Card>
          )}

          {data.kpl_enrichment?.length > 0 && (
            <Card size="small" title={`KPL 关联数据 (${data.kpl_enrichment.length}条)`}>
              <List
                size="small"
                dataSource={data.kpl_enrichment.slice(0, 10)}
                renderItem={(item: AnyData) => (
                  <List.Item>
                    <Space>
                      {item.stock_name && <Tag>{item.stock_name}</Tag>}
                      {item.stock_code && <Text code style={{ fontSize: 11 }}>{item.stock_code}</Text>}
                      {item.change_rate != null && (
                        <Text style={{ color: item.change_rate >= 0 ? '#f5222d' : '#52c41a' }}>
                          {item.change_rate > 0 ? '+' : ''}{item.change_rate.toFixed(2)}%
                        </Text>
                      )}
                      {item.reason && <Text type="secondary" style={{ fontSize: 12 }}>{item.reason}</Text>}
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          )}
        </>
      )}
    </div>
  )
}
