/**
 * AdminKplCookiePanel — 业主 KPL Cookie 录入面板
 *
 * M001/S03/T07 引入。挂在 AdminPage 顶层 Tabs 的 'KPL Cookie' tab 下。
 * Cookie 明文只在 POST 时离开浏览器一次（HTTPS + Bearer），后端写入
 * system_secrets 走 cookie_provider Fernet 加密。GET 永远只返回 metadata
 * （has_cookie / last_updated_at / last_ok_*），明文不会回到前端。
 *
 * 业主操作流程：
 *   1) 在 daban_pc app 抓包拿到 KPL Cookie 字符串
 *   2) 粘贴到下方 TextArea (≤4096 char)
 *   3) 点击「保存」→ 后端加密落库 + 自动触发一次健康探测
 *   4) 30 秒内观察上方双 HealthLight 转绿（apphwhq + apphis）
 *   5) 任一灯持续红色 → 点击「立即探测」手动重试
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  message,
  Space,
  Typography,
} from 'antd'

import { fetchApi, postApi } from '../api/client'
import HealthLight, { type HealthStatus } from '../components/HealthLight'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

interface CookieMetadata {
  has_cookie: boolean
  last_updated_at: string | null
  updated_by: number | null
  last_ok_realtime: string | null
  last_ok_history: string | null
}

interface HealthSnapshot {
  realtime: { status?: string; last_ok_at?: string | null }
  history: { status?: string; last_ok_at?: string | null }
}

const DEFAULT_META: CookieMetadata = {
  has_cookie: false,
  last_updated_at: null,
  updated_by: null,
  last_ok_realtime: null,
  last_ok_history: null,
}

function asHealthStatus(s: string | undefined): HealthStatus {
  if (s === 'ok' || s === 'fail' || s === 'stale') return s
  return 'unknown'
}

export default function AdminKplCookiePanel() {
  const [meta, setMeta] = useState<CookieMetadata>(DEFAULT_META)
  const [health, setHealth] = useState<HealthSnapshot>({
    realtime: { status: 'unknown' },
    history: { status: 'unknown' },
  })
  const [form] = Form.useForm<{ cookie: string }>()
  const [saving, setSaving] = useState(false)
  const [probing, setProbing] = useState(false)
  const [loading, setLoading] = useState(false)

  const refreshMeta = useCallback(async () => {
    setLoading(true)
    try {
      const m = await fetchApi<CookieMetadata>('/admin/kpl-cookie')
      setMeta(m || DEFAULT_META)
    } catch (e) {
      message.error((e as Error)?.message || '加载 Cookie 元数据失败')
      setMeta(DEFAULT_META)
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshHealth = useCallback(async () => {
    try {
      const h = await fetchApi<HealthSnapshot>('/admin/health/kpl')
      setHealth(h)
    } catch {
      setHealth({
        realtime: { status: 'unknown' },
        history: { status: 'unknown' },
      })
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshMeta()
    void refreshHealth()
  }, [refreshMeta, refreshHealth])

  const onSave = async () => {
    try {
      const v = await form.validateFields()
      const cookie = (v.cookie || '').trim()
      if (!cookie) {
        message.warning('Cookie 不能为空')
        return
      }
      if (cookie.length > 4096) {
        message.warning('Cookie 长度超过 4096 字符上限')
        return
      }
      setSaving(true)
      const r = await postApi<{
        success: boolean
        probe_triggered: boolean
        message?: string
      }>('/admin/kpl-cookie', { cookie })
      message.success(r.message || '已保存')
      form.resetFields()
      await refreshMeta()
      // 给后端 30s 健康探测一点时间，但不强制 sleep；用户会自然刷新
      await refreshHealth()
    } catch (e) {
      const err = e as Error
      if (err?.name === 'Error' && /validation/i.test(err.message)) return
      message.error(err?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const onProbe = async () => {
    setProbing(true)
    try {
      const r = await postApi<{
        success: boolean
        triggered: boolean
        reason?: string
      }>('/admin/health/kpl/trigger', {})
      if (r.triggered) {
        message.success('已触发本轮 KPL 健康探测')
      } else {
        message.warning(r.reason || '健康模块尚未就绪，将在下次 cron 周期触发')
      }
      await refreshHealth()
      await refreshMeta()
    } catch (e) {
      message.error((e as Error)?.message || '触发探测失败')
    } finally {
      setProbing(false)
    }
  }

  return (
    <div>
      <Title level={4}>KPL Cookie 配置</Title>
      <Paragraph type="secondary">
        KPL 实测参数依赖业主从 daban_pc 抓包获取的 Cookie 字符串。Cookie 加密
        存于 <Text code>system_secrets</Text>，后端永不在响应里返回明文。
      </Paragraph>

      <Card
        size="small"
        style={{ marginBottom: 16 }}
        title={
          <Space size="large">
            <span>实时状态</span>
            <HealthLight
              status={asHealthStatus(health.realtime?.status)}
              label="apphwhq (实时)"
              lastOkAt={health.realtime?.last_ok_at ?? meta.last_ok_realtime}
            />
            <HealthLight
              status={asHealthStatus(health.history?.status)}
              label="apphis (历史)"
              lastOkAt={health.history?.last_ok_at ?? meta.last_ok_history}
            />
          </Space>
        }
        extra={
          <Button onClick={onProbe} loading={probing}>
            立即探测
          </Button>
        }
      >
        {meta.has_cookie ? (
          <Alert
            type="success"
            showIcon
            message={`Cookie 已配置（更新于 ${meta.last_updated_at || '未知'}）`}
          />
        ) : (
          <Alert
            type="warning"
            showIcon
            message="尚未配置 KPL Cookie"
            description="短线 4 路由会返回 status='unavailable'，前端 DataStatusBadge 红色提示。请粘贴 daban_pc 抓包得到的 Cookie 字符串到下方表单。"
          />
        )}
      </Card>

      <Card title="录入 / 更新 Cookie" loading={loading} size="small">
        <Form form={form} layout="vertical" disabled={saving}>
          <Form.Item
            name="cookie"
            label="Cookie 字符串"
            rules={[
              { required: true, message: '请输入 Cookie' },
              { max: 4096, message: 'Cookie 长度不能超过 4096 字符' },
            ]}
          >
            <TextArea
              rows={4}
              maxLength={4096}
              placeholder="粘贴 daban_pc 抓包得到的完整 KPL Cookie 字符串"
              autoComplete="off"
              spellCheck={false}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" loading={saving} onClick={onSave}>
                保存
              </Button>
              <Button onClick={() => form.resetFields()} disabled={saving}>
                清空
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
