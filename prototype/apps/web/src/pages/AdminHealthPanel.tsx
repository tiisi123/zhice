/**
 * AdminHealthPanel — 业主健康监控
 *
 * M001/S03/T07 引入。挂在 AdminPage 顶层 Tabs 的 '健康监控' tab 下。展示：
 *   - 顶部 dual HealthLight (KPL realtime/apphwhq + KPL history/apphis)
 *     大尺寸 + last_ok_at 显示
 *   - 中部 system_alerts 未 ack 列表表格 (kind / level / message / created_at /
 *     action)
 *   - 「我已知悉」按钮 → POST /admin/alerts/{id}/ack → 行从未 ack 列表消失
 *
 * 数据来源:
 *   GET /api/admin/health/kpl          — T05 _HEALTH_CACHE 双键状态
 *   GET /api/admin/alerts?unresolved=1 — T03 system_alerts 表 + T05 持久化
 *   POST /api/admin/alerts/{id}/ack    — T04 单条 ack
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  message,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'

import { fetchApi, postApi } from '../api/client'
import HealthLight, { type HealthStatus } from '../components/HealthLight'

const { Title, Paragraph } = Typography

interface ProbeState {
  status?: string
  last_ok_at?: string | null
  last_error?: string | null
  consecutive_fail?: number
}

interface HealthSnapshot {
  realtime: ProbeState
  history: ProbeState
}

interface SystemAlert {
  id: number
  kind: string
  level?: string
  message: string
  meta?: string | Record<string, unknown> | null
  resolved_at: string | null
  created_at: string
}

interface AlertsResponse {
  alerts: SystemAlert[]
  count: number
}

function asHealthStatus(s: string | undefined): HealthStatus {
  if (s === 'ok' || s === 'fail' || s === 'stale') return s
  return 'unknown'
}

function levelTag(level?: string) {
  switch (level) {
    case 'critical':
      return <Tag color="red">严重</Tag>
    case 'warning':
      return <Tag color="orange">警告</Tag>
    case 'info':
      return <Tag color="blue">提示</Tag>
    default:
      return <Tag>—</Tag>
  }
}

export default function AdminHealthPanel() {
  const [health, setHealth] = useState<HealthSnapshot>({
    realtime: { status: 'unknown' },
    history: { status: 'unknown' },
  })
  const [alerts, setAlerts] = useState<SystemAlert[]>([])
  const [loading, setLoading] = useState(false)
  const [acking, setAcking] = useState<number | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [h, a] = await Promise.all([
        fetchApi<HealthSnapshot>('/admin/health/kpl'),
        fetchApi<AlertsResponse>('/admin/alerts', { unresolved: '1' }),
      ])
      setHealth(h)
      setAlerts(a?.alerts || [])
    } catch (e) {
      message.error((e as Error)?.message || '加载健康状态失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh()
  }, [refresh])

  const onAck = async (id: number) => {
    setAcking(id)
    try {
      await postApi<{ success: boolean }>(`/admin/alerts/${id}/ack`, {})
      message.success('已知悉')
      await refresh()
    } catch (e) {
      message.error((e as Error)?.message || 'ack 失败')
    } finally {
      setAcking(null)
    }
  }

  const realtimeBad = health.realtime?.status === 'fail'
  const historyBad = health.history?.status === 'fail'
  const anyBad = realtimeBad || historyBad

  return (
    <div>
      <Title level={4}>健康监控</Title>
      <Paragraph type="secondary">
        APScheduler 每 30 分钟探测一次 KPL realtime / history
        端点。任一灯转红
        会自动写入告警表并发送邮件给业主邮箱（参见 SMTP 模板 T06）。
      </Paragraph>

      <Card
        size="small"
        style={{ marginBottom: 16 }}
        title={
          <Space size="large">
            <HealthLight
              status={asHealthStatus(health.realtime?.status)}
              size="md"
              label="realtime (apphwhq)"
              lastOkAt={health.realtime?.last_ok_at ?? null}
            />
            <HealthLight
              status={asHealthStatus(health.history?.status)}
              size="md"
              label="history (apphis)"
              lastOkAt={health.history?.last_ok_at ?? null}
            />
          </Space>
        }
        extra={
          <Button onClick={refresh} loading={loading}>
            刷新
          </Button>
        }
      >
        {anyBad ? (
          <Alert
            type="error"
            showIcon
            message="KPL 数据源异常"
            description={
              <Descriptions size="small" column={2}>
                <Descriptions.Item label="realtime">
                  {health.realtime?.status} ·{' '}
                  {health.realtime?.last_error || '—'} (consecutive_fail=
                  {health.realtime?.consecutive_fail ?? 0})
                </Descriptions.Item>
                <Descriptions.Item label="history">
                  {health.history?.status} ·{' '}
                  {health.history?.last_error || '—'} (consecutive_fail=
                  {health.history?.consecutive_fail ?? 0})
                </Descriptions.Item>
              </Descriptions>
            }
          />
        ) : (
          <Alert
            type="success"
            showIcon
            message="所有 KPL 端点状态正常"
          />
        )}
      </Card>

      <Card title={`未处理告警 (${alerts.length})`} size="small">
        {alerts.length === 0 ? (
          <Empty description="暂无未处理告警" />
        ) : (
          <Table<SystemAlert>
            dataSource={alerts}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 20 }}
            columns={[
              { title: 'ID', dataIndex: 'id', width: 60 },
              { title: '类型', dataIndex: 'kind', width: 160 },
              {
                title: '级别',
                dataIndex: 'level',
                width: 90,
                render: (v?: string) => levelTag(v),
              },
              { title: '消息', dataIndex: 'message' },
              { title: '时间', dataIndex: 'created_at', width: 180 },
              {
                title: '操作',
                width: 110,
                render: (_: unknown, r: SystemAlert) => (
                  <Button
                    size="small"
                    loading={acking === r.id}
                    onClick={() => void onAck(r.id)}
                  >
                    我已知悉
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
