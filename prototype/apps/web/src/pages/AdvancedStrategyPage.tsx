import { useState } from 'react'
import { Card, Col, Row, Table, Statistic, Button, Select, Input, message, Popconfirm } from 'antd'
import { postApi, deleteApi, fetchApi } from '../api/client'
import Disclaimer from '../components/Disclaimer'

export default function AdvancedStrategyPage() {
  const [optResult, setOptResult] = useState<any>(null)
  const [simStatus, setSimStatus] = useState<any>(null)
  const [simId, setSimId] = useState('')
  const [loading, setLoading] = useState(false)
  const [template, setTemplate] = useState('涨停次日高开')
  const [buyCode, setBuyCode] = useState('000001')
  const [buyName, setBuyName] = useState('平安银行')
  const [buyPrice, setBuyPrice] = useState('12.5')
  const [buyAmount, setBuyAmount] = useState('100000')
  const [sellCode, setSellCode] = useState('')
  const [sellPrice, setSellPrice] = useState('')

  const runOptimize = async () => {
    setLoading(true)
    try {
      const data = await postApi<any>(`/advanced-strategy/optimize?template_name=${encodeURIComponent(template)}&years=3`)
      setOptResult(data)
      if (data.data_status === 'unavailable') message.warning(data.message || '真实历史行情不可用')
    } catch (e: any) {
      message.error(e.message || '参数优化失败')
    }
    setLoading(false)
  }

  const createSim = async () => {
    try {
      const data = await postApi<any>('/advanced-strategy/sim/create?capital=1000000')
      setSimId(data.session_id)
      setSimStatus(data.status)
      message.success(`模拟账户创建成功: ${data.session_id}`)
    } catch (e: any) {
      message.error(e.message || '创建模拟账户失败')
    }
  }

  const simNextDay = async () => {
    if (!simId) return
    try {
      const data = await postApi<any>(`/advanced-strategy/sim/${simId}/next-day`)
      setSimStatus(data.status)
    } catch (e: any) {
      message.error(e.message || '推进失败')
    }
  }

  const simBuy = async () => {
    if (!simId) return
    try {
      const data = await postApi<any>(
        `/advanced-strategy/sim/${simId}/buy?code=${buyCode}&name=${encodeURIComponent(buyName)}&price=${buyPrice}&amount=${buyAmount}`
      )
      setSimStatus(data.status)
      message.success('买入成功')
    } catch (e: any) {
      message.error(e.message || '买入失败')
    }
  }

  const simSell = async () => {
    if (!simId || !sellCode || !sellPrice) {
      message.warning('请填写卖出代码和价格')
      return
    }
    try {
      const data = await postApi<any>(
        `/advanced-strategy/sim/${simId}/sell?code=${sellCode}&price=${sellPrice}`
      )
      setSimStatus(data.status)
      message.success(`卖出成功，盈亏: ${data.trade?.pnl || 0}`)
    } catch (e: any) {
      message.error(e.message || '卖出失败')
    }
  }

  const deleteSim = async () => {
    if (!simId) return
    try {
      await deleteApi(`/advanced-strategy/sim/${simId}`)
      setSimId('')
      setSimStatus(null)
      message.success('模拟账户已删除')
    } catch (e: any) {
      message.error(e.message || '删除失败')
    }
  }

  const refreshStatus = async () => {
    if (!simId) return
    try {
      const data = await fetchApi<any>(`/advanced-strategy/sim/${simId}/status`)
      setSimStatus(data.status)
    } catch (e: any) {
      message.error(e.message || '刷新失败')
    }
  }

  const optCols = [
    { title: '止盈', dataIndex: 'take_profit', width: 50, render: (v: number) => `${v}%` },
    { title: '止损', dataIndex: 'stop_loss', width: 50, render: (v: number) => `${v}%` },
    { title: '持有天', dataIndex: 'hold_days', width: 60 },
    { title: '总收益', dataIndex: 'total_return', width: 70, render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v}%</span> },
    { title: '夏普', dataIndex: 'sharpe_ratio', width: 50 },
    { title: '胜率', dataIndex: 'win_rate', width: 60, render: (v: number) => `${v}%` },
    { title: '回撤', dataIndex: 'max_drawdown', width: 60, render: (v: number) => `${v}%` },
  ]

  return (
    <div>
      <h2>高级策略工具</h2>
      <Disclaimer kind="backtest" />
      <Row gutter={16}>
        <Col span={12}>
          <Card title="参数优化 (网格搜索)" size="small" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <Select value={template} onChange={setTemplate} style={{ width: 200 }}
                options={['涨停次日高开', '连板龙头低吸', '题材轮动跟随'].map(n => ({ label: n, value: n }))} />
              <Button type="primary" onClick={runOptimize} loading={loading}>运行优化</Button>
            </div>
            {optResult && (
              <>
                <p>共测试 {optResult.total_combinations} 种参数组合</p>
                <h4>最佳 5 组</h4>
                <Table dataSource={optResult.best_5} columns={optCols} rowKey={(_, i) => String(i)} size="small" pagination={false} />
                <h4 style={{ marginTop: 12 }}>最差 3 组</h4>
                <Table dataSource={optResult.worst_3} columns={optCols} rowKey={(_, i) => `w${i}`} size="small" pagination={false} />
              </>
            )}
          </Card>
        </Col>

        <Col span={12}>
          <Card title="模拟交易" size="small">
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
              <Button onClick={createSim} type="primary">创建模拟账户</Button>
              {simId && <>
                <Button onClick={simNextDay}>推进1天</Button>
                <Button onClick={refreshStatus}>刷新状态</Button>
                <Popconfirm title="确认删除?" onConfirm={deleteSim}>
                  <Button danger>删除账户</Button>
                </Popconfirm>
              </>}
            </div>

            {simId && (
              <>
                <Card size="small" type="inner" title="买入" style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    <Input value={buyCode} onChange={e => setBuyCode(e.target.value)} placeholder="代码" style={{ width: 80 }} />
                    <Input value={buyName} onChange={e => setBuyName(e.target.value)} placeholder="名称" style={{ width: 80 }} />
                    <Input value={buyPrice} onChange={e => setBuyPrice(e.target.value)} placeholder="价格" style={{ width: 70 }} />
                    <Input value={buyAmount} onChange={e => setBuyAmount(e.target.value)} placeholder="金额" style={{ width: 80 }} />
                    <Button type="primary" onClick={simBuy} size="small">买入</Button>
                  </div>
                </Card>
                <Card size="small" type="inner" title="卖出" style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <Input value={sellCode} onChange={e => setSellCode(e.target.value)} placeholder="代码" style={{ width: 80 }} />
                    <Input value={sellPrice} onChange={e => setSellPrice(e.target.value)} placeholder="价格" style={{ width: 80 }} />
                    <Button danger onClick={simSell} size="small">卖出</Button>
                  </div>
                </Card>
              </>
            )}

            {simStatus && (
              <>
                <Row gutter={[8, 8]} style={{ marginTop: 8 }}>
                  <Col span={8}><Statistic title="总资产" value={simStatus.total_value} precision={0} /></Col>
                  <Col span={8}><Statistic title="收益率" value={simStatus.total_return} suffix="%" precision={2}
                    valueStyle={{ color: simStatus.total_return >= 0 ? '#f5222d' : '#52c41a' }} /></Col>
                  <Col span={8}><Statistic title="第N天" value={simStatus.day} /></Col>
                </Row>
                {simStatus.positions?.length > 0 && (
                  <Table dataSource={simStatus.positions} rowKey="code" size="small" pagination={false} style={{ marginTop: 8 }}
                    columns={[
                      { title: '代码', dataIndex: 'code', width: 70 },
                      { title: '名称', dataIndex: 'name', width: 80 },
                      { title: '现价', dataIndex: 'current_price', width: 70 },
                      { title: '市值', dataIndex: 'value', width: 80 },
                    ]} />
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>
      <div style={{ marginTop: 12, color: '#faad14', fontSize: 12 }}>参数优化仅在真实历史行情可用时展示；右侧为手动录入价格的模拟交易账户，结果仅供流程演练。</div>
    </div>
  )
}
