/**
 * 功能地图（运营自检用）：
 * 左侧选择页面 → 右侧实时加载该页 iframe，叠加红色画框 + PRD ID 标签。
 * 数据驱动：所有标注由 FEATURE_MAP 配置；rect 用相对百分比，分辨率自适应。
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Card, Typography, Select, Switch, Tag, Space, Empty, Button, Input, message } from 'antd'
import { ReloadOutlined, LinkOutlined, ExpandOutlined, CameraOutlined, DownloadOutlined, FileZipOutlined } from '@ant-design/icons'
import html2canvas from 'html2canvas'
import JSZip from 'jszip'
import type { AnyData } from '../api/types'

const { Title, Paragraph, Text } = Typography

type Box = {
  ids: string[]
  name: string
  /** 模式 A：DOM 选择器（推荐）。匹配 iframe 内 [data-feature='...'] 的元素。 */
  selector?: string
  /** 模式 B：相对百分比 [x%, y%, w%, h%]，作为 selector 不命中时的兜底。 */
  rect?: [number, number, number, number]
  color?: string
}

type LiveBox = Box & { rect: [number, number, number, number]; resolved: boolean }

type PageMap = {
  slug: string                // 路由
  title: string               // 页面标题
  group: string               // 模块分组
  desc?: string
  boxes: Box[]
}

const RED = '#f5222d'
const ORANGE = '#fa8c16'
const BLUE = '#1677ff'
const GREEN = '#13c2c2'
const PURPLE = '#722ed1'

const FEATURE_MAP: PageMap[] = [
  {
    slug: '/replay', title: '收盘复盘', group: '短线/热点',
    desc: '主线：一句话速报 → 三幕故事 → 情绪温度 → 主线 → 连板梯队 → 资金 → 明日（已用 data-feature 精确对齐）',
    boxes: [
      { ids: ['AI-Headline'], name: 'AI 一句话速报', selector: '[data-feature="AI-Headline"]', color: PURPLE },
      { ids: ['新增'], name: '今日故事线（三幕）', selector: '[data-feature="Storyline"]', color: ORANGE },
      { ids: ['M1-01', 'M4A-01'], name: '市场温度仪表盘 + 30 日趋势', selector: '[data-feature="M1-01,M4A-01"]', color: RED },
      { ids: ['M2-02', 'M4B-02'], name: '主线题材 Top3 + 板块散点', selector: '[data-feature="M2-02,M4B-02"]', color: ORANGE },
      { ids: ['M1-02', 'M4A-03'], name: '连板天梯 + 接力漏斗', selector: '[data-feature="M1-02,M4A-03"]', color: RED },
      { ids: ['M1-04'], name: '资金流向（默认折叠）', selector: '[data-feature="M1-04"]', color: BLUE },
      { ids: ['M4A-08', 'M1-06'], name: '明日策略 + AI 追问', selector: '[data-feature="M4A-08,M1-06"]', color: GREEN },
    ],
  },
  {
    slug: '/intraday', title: '盘中盯盘', group: '短线/热点',
    boxes: [
      { ids: ['M1-05'], name: '左侧 · 异动流（实时刷新）', rect: [0, 8, 22, 90], color: PURPLE },
      { ids: ['M1-02', 'M4A-02'], name: '中央 · 涨停实时扫描', rect: [22, 8, 50, 60], color: RED },
      { ids: ['M4A-04'], name: '中央 Tab · 炸板/撬板', rect: [22, 8, 50, 8], color: ORANGE },
      { ids: ['M2-01'], name: '可视化 Tab · 板块轮动散点', rect: [22, 8, 50, 8], color: BLUE },
      { ids: ['M1-03'], name: '右侧 · 板块涨跌排行', rect: [72, 8, 28, 90], color: GREEN },
    ],
  },
  {
    slug: '/sentiment', title: '情绪周期', group: '短线/热点',
    boxes: [
      { ids: ['M2-06'], name: '情绪曲线（涨停+炸板+连板高度）', rect: [0, 10, 100, 50], color: RED },
      { ids: ['新增'], name: '相似日匹配 / 阶段判断', rect: [0, 62, 100, 36], color: BLUE },
    ],
  },
  {
    slug: '/theme', title: '题材板块', group: '短线/热点',
    boxes: [
      { ids: ['M2-02', 'M4B-02'], name: '题材热度排行表', rect: [0, 8, 60, 90], color: RED },
      { ids: ['M4B-03'], name: '题材详情（点击行展开）', rect: [60, 8, 40, 90], color: ORANGE },
    ],
  },
  {
    slug: '/broken-cases', title: '炸板案例库', group: '短线/热点',
    boxes: [
      { ids: ['M4A-09'], name: '炸板案例（按原因分类 + 搜索）', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/longhu', title: '龙虎榜', group: '短线/热点',
    boxes: [
      { ids: ['M4A-11'], name: '知名席位买卖明细', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/rotation', title: '轮动推演', group: '短线/热点',
    boxes: [
      { ids: ['M2-05', 'M4B-07'], name: 'Tab · 轮动推演（A 启动 → B/C 概率）', rect: [0, 8, 100, 6], color: RED },
      { ids: ['M4B-06'], name: 'Tab · 传导路径', rect: [0, 8, 100, 6], color: ORANGE },
      { ids: ['M4B-09'], name: 'Tab · 预期差评估', rect: [0, 8, 100, 6], color: BLUE },
      { ids: ['M4B-10'], name: 'Tab · 新题材识别', rect: [0, 8, 100, 6], color: GREEN },
      { ids: ['M4B-11'], name: 'Tab · 题材历史复盘', rect: [0, 8, 100, 6], color: PURPLE },
    ],
  },
  {
    slug: '/chain', title: '产业链图谱', group: '短线/热点',
    boxes: [
      { ids: ['M2-03', 'M4B-05'], name: 'ECharts 关系图（点击节点展开成分股）', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/growth', title: '景气度分析', group: '成长/价值',
    boxes: [
      { ids: ['M4C-01'], name: '宏观面板（PMI/PPI/CPI…）', rect: [0, 8, 100, 25], color: BLUE },
      { ids: ['M4C-02'], name: '行业景气度热力图', rect: [0, 34, 100, 30], color: ORANGE },
      { ids: ['M4C-03'], name: '中观追踪（产量/价格/库存）', rect: [0, 65, 50, 33], color: GREEN },
      { ids: ['M4C-05'], name: '行业比较', rect: [50, 65, 50, 33], color: RED },
    ],
  },
  {
    slug: '/prosperity', title: '景气度中心', group: '成长/价值',
    desc: '六大 Tab，逐项核对景气度 P0 功能',
    boxes: [
      { ids: ['M4C-06'], name: 'Tab · 扩散指数', rect: [0, 12, 16, 6], color: BLUE },
      { ids: ['M4C-04'], name: 'Tab · 拐点预警', rect: [16, 12, 16, 6], color: ORANGE },
      { ids: ['M4C-07'], name: 'Tab · 宏观传导（新增）', rect: [32, 12, 16, 6], color: RED },
      { ids: ['M4C-08'], name: 'Tab · 产业链景气（新增）', rect: [48, 12, 16, 6], color: RED },
      { ids: ['M4C-09'], name: 'Tab · AI 周报', rect: [64, 12, 16, 6], color: PURPLE },
      { ids: ['M4C-10'], name: 'Tab · 历史周期', rect: [80, 12, 16, 6], color: GREEN },
    ],
  },
  {
    slug: '/etf-rotation', title: 'ETF 轮动', group: '成长/价值',
    boxes: [
      { ids: ['新增'], name: 'ETF 多周期轮动评分 + 仪表盘', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/value', title: '价值/持仓', group: '成长/价值',
    boxes: [
      { ids: ['M4D-01'], name: '持仓仪表盘', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/valuation', title: '估值分析', group: '成长/价值',
    boxes: [
      { ids: ['M4D-10'], name: '顶部 · 价值股筛选条件', rect: [0, 8, 100, 8], color: PURPLE },
      { ids: ['M4D-02'], name: '财报数据', rect: [0, 17, 50, 22], color: BLUE },
      { ids: ['M4D-06'], name: 'DCF / PE / PB 估值', rect: [50, 17, 50, 22], color: RED },
      { ids: ['M4D-09'], name: '财务预测三档', rect: [0, 40, 50, 22], color: ORANGE },
      { ids: ['M4D-11', 'M4C-11'], name: '卖方预期 / 修正历史', rect: [50, 40, 50, 22], color: GREEN },
      { ids: ['M4D-08'], name: '另类数据', rect: [0, 63, 50, 18], color: BLUE },
      { ids: ['M4D-07'], name: '预期差', rect: [50, 63, 50, 18], color: PURPLE },
      { ids: ['M4D-05'], name: 'AI 财报解读按钮', rect: [0, 82, 100, 16], color: RED },
    ],
  },
  {
    slug: '/research', title: '研究中心', group: '成长/价值',
    boxes: [
      { ids: ['M4D-03', 'M4B-01'], name: 'Tab · 公告 / 事件日历', rect: [0, 12, 25, 6], color: BLUE },
      { ids: ['M4D-04'], name: 'Tab · 研报追踪', rect: [25, 12, 25, 6], color: ORANGE },
      { ids: ['M4D-08'], name: 'Tab · 另类数据', rect: [50, 12, 25, 6], color: GREEN },
      { ids: ['M4D-05'], name: '财报 AI 解读', rect: [75, 12, 25, 6], color: RED },
    ],
  },
  {
    slug: '/strategy', title: '策略回测', group: '工具',
    boxes: [
      { ids: ['M3-03'], name: '模板下拉（含 M4A-07 打板模板）', rect: [0, 8, 100, 8], color: PURPLE },
      { ids: ['M3-02', 'M4A-07'], name: '回测引擎 + 7 项指标', rect: [0, 18, 100, 80], color: RED },
    ],
  },
  {
    slug: '/strategy-builder', title: '可视化构建器', group: '工具',
    boxes: [
      { ids: ['M3-01'], name: '条件卡片 + 参数滑块 → 生成 DSL', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/advanced-strategy', title: '高级策略', group: '工具',
    boxes: [
      { ids: ['M3-05'], name: 'Tab · 参数优化（网格搜索）', rect: [0, 12, 50, 6], color: ORANGE },
      { ids: ['M3-06'], name: 'Tab · 模拟交易（撮合）', rect: [50, 12, 50, 6], color: BLUE },
    ],
  },
  {
    slug: '/recommend', title: '策略推荐', group: '工具',
    boxes: [
      { ids: ['M3-04'], name: 'AI 策略推荐（基于风格 + 行为）', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/lab', title: '策略实验室', group: '工具',
    boxes: [
      { ids: ['M3-07'], name: 'Tab · 策略对比（最多 5 条）', rect: [0, 12, 33, 6], color: BLUE },
      { ids: ['M4A-10'], name: 'Tab · 自定义打板规则', rect: [33, 12, 34, 6], color: ORANGE },
      { ids: ['M4E-03', 'M4E-04', 'M4E-05'], name: 'Tab · 多风格组合 / 学习', rect: [67, 12, 33, 6], color: PURPLE },
    ],
  },
  {
    slug: '/dashboard', title: '自定义看板', group: '工具',
    boxes: [
      { ids: ['M1-08'], name: '左侧 · 组件目录（拖入即用）', rect: [0, 8, 25, 90], color: BLUE },
      { ids: ['M1-08'], name: '中央 · 看板画布（最多 20 组件）', rect: [25, 8, 75, 90], color: RED },
    ],
  },
  {
    slug: '/report-archive', title: '报告存档', group: '工具',
    boxes: [
      { ids: ['M1-07'], name: '历史复盘 · 按日期/搜索/导出', rect: [0, 8, 100, 90], color: RED },
    ],
  },
  {
    slug: '/vip', title: 'VIP 会员中心', group: '工具',
    boxes: [
      { ids: ['U-02'], name: '免费 / 标准 / 专业 三档', rect: [0, 8, 100, 60], color: ORANGE },
      { ids: ['U-03'], name: '微信支付开通入口', rect: [0, 70, 100, 28], color: RED },
    ],
  },
  {
    slug: '/stock/600519', title: '个股分析（示例：贵州茅台）', group: '工具',
    boxes: [
      { ids: ['个股-01'], name: '题材归属', rect: [0, 8, 100, 12], color: BLUE },
      { ids: ['个股-02'], name: '涨停原因 / 催化', rect: [0, 21, 100, 12], color: ORANGE },
      { ids: ['个股-03'], name: '资金流向', rect: [0, 34, 100, 14], color: GREEN },
      { ids: ['个股-04', 'M4A-06'], name: 'K 线形态 + 模式匹配', rect: [0, 49, 100, 30], color: RED },
      { ids: ['个股-05'], name: 'AI 摘要', rect: [0, 80, 100, 18], color: PURPLE },
    ],
  },
  {
    slug: '/onboarding', title: '风格问卷', group: '风格',
    boxes: [
      { ids: ['M4E-01'], name: '5 题快速测试 → 推荐风格', rect: [0, 8, 100, 90], color: RED },
    ],
  },
]

const GROUPS = ['短线/热点', '成长/价值', '工具', '风格']

export default function FeatureMapPage() {
  const [slug, setSlug] = useState('/replay')
  const [showBoxes, setShowBoxes] = useState(true)
  const [filter, setFilter] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [liveBoxes, setLiveBoxes] = useState<LiveBox[]>([])
  const [flashIdx, setFlashIdx] = useState<number | null>(null)
  const [iframeReady, setIframeReady] = useState(0)
  const iframeReadyRef = useRef(0)
  useEffect(() => { iframeReadyRef.current = iframeReady }, [iframeReady])

  const current = useMemo(() => FEATURE_MAP.find(p => p.slug === slug)!, [slug])

  const filteredBoxes = useMemo(() => {
    if (!filter.trim()) return current.boxes
    const f = filter.toLowerCase()
    return current.boxes.filter(b =>
      b.name.toLowerCase().includes(f) ||
      b.ids.some(id => id.toLowerCase().includes(f))
    )
  }, [current, filter])

  // 解析每个 box 在 iframe 视口中的实际位置（px → %）。
  // selector 命中时用真实坐标；否则回退到配置的 rect。
  const recompute = () => {
    const iframe = iframeRef.current
    if (!iframe) return
    const iw = iframe.clientWidth
    const ih = iframe.clientHeight
    let doc: Document | null = null
    try { doc = iframe.contentDocument } catch { doc = null }

    const next: LiveBox[] = filteredBoxes.map(b => {
      if (b.selector && doc) {
        const el = doc.querySelector(b.selector) as HTMLElement | null
        if (el) {
          const r = el.getBoundingClientRect()
          // 限制不超出 iframe 视口
          const x = Math.max(0, (r.left / iw) * 100)
          const y = Math.max(0, (r.top / ih) * 100)
          const w = Math.min(100 - x, (r.width / iw) * 100)
          const h = Math.min(100 - y, (r.height / ih) * 100)
          return { ...b, rect: [x, y, w, h], resolved: true }
        }
      }
      return { ...b, rect: b.rect ?? [0, 0, 0, 0], resolved: false }
    })
    setLiveBoxes(next)
  }

  // iframe 装载 / 选项变化 → 重算
  useEffect(() => {
    recompute()
    // 监听 iframe 内部滚动（同源时可访问）
    const iframe = iframeRef.current
    if (!iframe) return
    let win: Window | null = null
    try { win = iframe.contentWindow } catch { /* cross-origin iframe — fall through to !win check */ }
    if (!win) return
    const onScroll = () => recompute()
    win.addEventListener('scroll', onScroll, true)
    win.addEventListener('resize', onScroll)
    const t = setInterval(recompute, 1500) // 兜底：动态内容重算
    return () => {
      try { win?.removeEventListener('scroll', onScroll, true) } catch { /* iframe gone */ }
      try { win?.removeEventListener('resize', onScroll) } catch { /* iframe gone */ }
      clearInterval(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [iframeReady, slug, filter, refreshKey, current])

  // ===== 导出带标注的 PNG（一键截图） =====
  const [exporting, setExporting] = useState(false)

  const drawAnnotations = (
    ctx: CanvasRenderingContext2D,
    boxes: Box[],
    doc: Document,
    win: Window,
    fullPage: boolean,
  ) => {
    for (const b of boxes) {
      let pageRect: { x: number; y: number; w: number; h: number } | null = null
      if (b.selector) {
        const el = doc.querySelector(b.selector) as HTMLElement | null
        if (el) {
          const r = el.getBoundingClientRect()
          pageRect = {
            x: r.left + (fullPage ? win.scrollX : 0),
            y: r.top + (fullPage ? win.scrollY : 0),
            w: r.width,
            h: r.height,
          }
        }
      } else if (b.rect) {
        const [x, y, w, h] = b.rect
        const iw = win.innerWidth
        const ih = win.innerHeight
        pageRect = { x: x / 100 * iw, y: y / 100 * ih, w: w / 100 * iw, h: h / 100 * ih }
      }
      if (!pageRect || pageRect.w <= 0 || pageRect.h <= 0) continue

      const color = b.color || RED
      ctx.save()
      ctx.lineWidth = 3
      ctx.setLineDash([10, 5])
      ctx.strokeStyle = color
      ctx.strokeRect(pageRect.x, pageRect.y, pageRect.w, pageRect.h)

      // 标签
      ctx.setLineDash([])
      const label = `${b.ids.join(' / ')} · ${b.name}`
      ctx.font = 'bold 14px -apple-system, "Microsoft YaHei", sans-serif'
      const metrics = ctx.measureText(label)
      const labelW = Math.min(metrics.width + 16, pageRect.w)
      const labelH = 24
      ctx.fillStyle = color
      ctx.fillRect(pageRect.x, pageRect.y, labelW, labelH)
      ctx.fillStyle = '#fff'
      ctx.textBaseline = 'middle'
      // 裁切，避免溢出
      ctx.beginPath()
      ctx.rect(pageRect.x, pageRect.y, labelW, labelH)
      ctx.clip()
      ctx.fillText(label, pageRect.x + 8, pageRect.y + labelH / 2 + 1)
      ctx.restore()
    }
  }

  const triggerDownload = (canvas: HTMLCanvasElement, filename: string) => {
    canvas.toBlob(blob => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }, 'image/png')
  }

  const fileStamp = () => {
    const d = new Date()
    const p = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`
  }

  /** 渲染 PNG。download=true 直接触发下载；否则返回 Blob 供 ZIP 打包。 */
  const renderPng = async (
    pageMap: PageMap,
    mode: 'full' | 'viewport',
    download: boolean,
  ): Promise<{ blob: Blob; filename: string } | null> => {
    const iframe = iframeRef.current
    if (!iframe) return null
    let doc: Document | null = null
    let win: Window | null = null
    try { doc = iframe.contentDocument; win = iframe.contentWindow } catch { /* cross-origin iframe — handled below */ }
    if (!doc || !win) { message.error('iframe 不可访问'); return null }

    const isFull = mode === 'full'
    const w = isFull ? doc.documentElement.scrollWidth : win.innerWidth
    const h = isFull ? doc.documentElement.scrollHeight : win.innerHeight

    const canvas = await html2canvas(doc.body, {
      width: w, height: h,
      windowWidth: w, windowHeight: h,
      x: isFull ? 0 : win.scrollX,
      y: isFull ? 0 : win.scrollY,
      backgroundColor: '#ffffff',
      scale: window.devicePixelRatio || 1,
      useCORS: true, logging: false,
    })

    const ctx = canvas.getContext('2d')
    if (ctx) {
      const scale = canvas.width / w
      ctx.save()
      ctx.scale(scale, scale)
      const offsetWin: Window = isFull ? win : ({
        ...win,
        scrollX: 0, scrollY: 0,
        innerWidth: win.innerWidth, innerHeight: win.innerHeight,
      } as AnyData)
      drawAnnotations(ctx, pageMap.boxes, doc, offsetWin, isFull)
      ctx.restore()
    }

    const filename = `featuremap-${pageMap.title}-${mode}-${fileStamp()}.png`
      .replace(/[\\/:*?"<>|]/g, '_')

    if (download) {
      triggerDownload(canvas, filename)
      return null
    }
    const blob: Blob = await new Promise((resolve, reject) => {
      canvas.toBlob(b => b ? resolve(b) : reject(new Error('toBlob 失败')), 'image/png')
    })
    return { blob, filename }
  }

  const exportPngFor = async (pageMap: PageMap, mode: 'full' | 'viewport') => {
    await renderPng(pageMap, mode, true)
  }

  const exportPng = async (mode: 'full' | 'viewport') => {
    setExporting(true)
    const hide = message.loading(`正在生成${mode === 'full' ? '整页' : '当前视口'}标注截图...`, 0)
    try {
      await exportPngFor(current, mode)
      message.success('已导出 PNG')
    } catch (e) {
      console.error(e)
      message.error('导出失败：' + ((e as Error)?.message || '未知错误'))
    } finally {
      hide()
      setExporting(false)
    }
  }

  // 等 iframe 重新载入完成（轮询 ref，避免闭包旧值）
  const waitForIframeReady = (initialReady: number, timeoutMs = 8000): Promise<void> => {
    const start = Date.now()
    return new Promise((resolve, reject) => {
      const tick = () => {
        if (iframeReadyRef.current !== initialReady) return resolve()
        if (Date.now() - start > timeoutMs) return reject(new Error('iframe 加载超时'))
        setTimeout(tick, 200)
      }
      tick()
    })
  }

  /** 批量导出：packMode=true 打成单个 ZIP；false 逐张下载 */
  const exportAllPages = async (packMode: boolean) => {
    setExporting(true)
    const hide = message.loading(
      `即将批量导出 ${FEATURE_MAP.length} 页${packMode ? '并打包 ZIP' : ''}，约需 ${FEATURE_MAP.length * 5} 秒...`, 0,
    )
    const zip = packMode ? new JSZip() : null
    let done = 0
    const failed: string[] = []
    try {
      for (const p of FEATURE_MAP) {
        const before = iframeReadyRef.current
        setSlug(p.slug)
        try { await waitForIframeReady(before) } catch { /* timeout 也继续 */ }
        await new Promise(r => setTimeout(r, 1800)) // 等数据加载
        try {
          if (packMode) {
            const r = await renderPng(p, 'full', false)
            if (r) zip!.file(r.filename, r.blob)
          } else {
            await renderPng(p, 'full', true)
          }
          done++
        } catch (e) {
          console.warn(`导出 ${p.title} 失败：`, e)
          failed.push(p.title)
        }
        await new Promise(r => setTimeout(r, 300))
      }

      if (packMode && zip && done > 0) {
        const blob = await zip.generateAsync({ type: 'blob' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `featuremap-all-${fileStamp()}.zip`
        document.body.appendChild(a)
        a.click()
        a.remove()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      }

      const failMsg = failed.length ? `（失败：${failed.join('、')}）` : ''
      message.success(`批量导出完成 ${done}/${FEATURE_MAP.length} 页${failMsg}`)
    } finally {
      hide()
      setExporting(false)
    }
  }

  // 点击左侧标注：滚动 iframe 到对应元素并闪烁
  const focusBox = (idx: number) => {
    setFlashIdx(idx)
    const b = filteredBoxes[idx]
    const iframe = iframeRef.current
    if (b?.selector && iframe) {
      try {
        const el = iframe.contentDocument?.querySelector(b.selector) as HTMLElement | null
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } catch { /* selector failed — ignore */ }
    }
    setTimeout(() => setFlashIdx(null), 1800)
  }

  return (
    <div>
      <Title level={3} style={{ marginBottom: 4 }}>功能地图 · 运营自检</Title>
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        左侧选择页面，右侧实时载入并叠加 PRD 功能标注。鼠标悬停画框可查看功能 ID 与说明。
      </Paragraph>

      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 220px)', minHeight: 600 }}>
        {/* 左侧：页面选择 + 标注列表 */}
        <Card size="small" style={{ width: 320, flexShrink: 0, overflow: 'auto' }}
          styles={{ body: { padding: 12 } }}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Select
              value={slug} onChange={setSlug} style={{ width: '100%' }}
              optionFilterProp="label" showSearch
              options={GROUPS.map(g => ({
                label: g,
                options: FEATURE_MAP.filter(p => p.group === g).map(p => ({
                  value: p.slug, label: `${p.title}  ·  ${p.slug}`,
                })),
              }))}
            />
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12 }}>显示画框</span>
              <Switch checked={showBoxes} onChange={setShowBoxes} size="small" />
            </Space>
            <Input.Search
              placeholder="按 ID 或名称过滤" allowClear size="small"
              onChange={e => setFilter(e.target.value)} value={filter}
            />
            <Button size="small" icon={<ReloadOutlined />} onClick={() => setRefreshKey(k => k + 1)} block>
              重载页面
            </Button>
            <Button size="small" icon={<LinkOutlined />} block onClick={() => window.open(slug, '_blank')}>
              在新标签打开
            </Button>
            <div style={{ height: 1, background: '#f0f0f0', margin: '4px 0' }} />
            <Button
              size="small" type="primary" icon={<CameraOutlined />} block
              loading={exporting} onClick={() => exportPng('viewport')}
            >
              导出当前视口 PNG
            </Button>
            <Button
              size="small" icon={<DownloadOutlined />} block
              loading={exporting} onClick={() => exportPng('full')}
            >
              导出整页 PNG（含滚动）
            </Button>
            <Button
              size="small" type="primary" ghost icon={<FileZipOutlined />} block
              loading={exporting}
              onClick={() => exportAllPages(true)}
            >
              批量打包 ZIP（{FEATURE_MAP.length} 页）
            </Button>
            <Button
              size="small" type="dashed" block
              loading={exporting}
              onClick={() => exportAllPages(false)}
            >
              批量逐张下载（{FEATURE_MAP.length} 页）
            </Button>
          </Space>

          <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
            {current.desc && <Paragraph type="secondary" style={{ fontSize: 11, marginBottom: 8 }}>{current.desc}</Paragraph>}
            <div style={{ fontWeight: 600, marginBottom: 6 }}>
              {current.title} 共 {filteredBoxes.length} / {current.boxes.length} 项标注
            </div>
            {filteredBoxes.map((b, i) => {
              const live = liveBoxes[i]
              const isResolved = live?.resolved
              return (
                <div key={i}
                  onClick={() => focusBox(i)}
                  style={{
                    padding: '6px 8px', borderLeft: `3px solid ${b.color || RED}`,
                    background: flashIdx === i ? '#fff7e6' : '#fafafa',
                    marginBottom: 4, borderRadius: 4, cursor: 'pointer',
                    transition: 'background 0.2s',
                  }}>
                  <div>
                    {b.ids.map(id => (
                      <Tag key={id} color={b.color || 'red'} style={{ marginRight: 4 }}>{id}</Tag>
                    ))}
                    {b.selector && (
                      <Tag color={isResolved ? 'green' : 'default'} style={{ fontSize: 10 }}>
                        {isResolved ? '✓ 已对齐' : '⊘ 未命中'}
                      </Tag>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: '#262626', marginTop: 2 }}>{b.name}</div>
                </div>
              )
            })}
            {filteredBoxes.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </div>
        </Card>

        {/* 右侧：iframe + 叠加层 */}
        <Card size="small" style={{ flex: 1, overflow: 'hidden' }} styles={{ body: { padding: 0, height: '100%' } }}>
          <div style={{ position: 'relative', width: '100%', height: '100%', background: '#000' }}>
            <iframe
              ref={iframeRef}
              key={`${slug}-${refreshKey}`}
              src={`${slug}${slug.includes('?') ? '&' : '?'}embed=1`}
              title={current.title}
              onLoad={() => setIframeReady(k => k + 1)}
              style={{ width: '100%', height: '100%', border: 0, background: '#fff' }}
            />
            {showBoxes && (
              <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
                {liveBoxes.map((b, i) => {
                  const [x, y, w, h] = b.rect
                  if (w <= 0 || h <= 0) return null
                  const color = b.color || RED
                  const isFlash = flashIdx === i
                  return (
                    <div key={i} style={{
                      position: 'absolute', left: `${x}%`, top: `${y}%`, width: `${w}%`, height: `${h}%`,
                      border: `${isFlash ? 3 : 2}px dashed ${color}`,
                      background: isFlash ? `${color}40` : `${color}10`,
                      pointerEvents: 'auto', cursor: 'help',
                      transition: 'all 0.2s',
                      boxShadow: isFlash ? `0 0 0 4px ${color}33` : 'none',
                    }}
                    title={`${b.ids.join(' / ')}  ·  ${b.name}${b.resolved ? '  · 已对齐 DOM' : ''}`}
                    onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = `${color}30` }}
                    onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = isFlash ? `${color}40` : `${color}10` }}
                    >
                      <div style={{
                        position: 'absolute', top: -1, left: -1,
                        background: color, color: '#fff', fontSize: 11, fontWeight: 600,
                        padding: '2px 6px', borderRadius: '0 0 4px 0', whiteSpace: 'nowrap',
                        maxWidth: '95%', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {b.ids.join(' / ')} · {b.name}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            <div style={{
              position: 'absolute', right: 12, bottom: 12, background: 'rgba(0,0,0,0.6)',
              color: '#fff', padding: '4px 10px', borderRadius: 4, fontSize: 11,
            }}>
              <ExpandOutlined /> <Text style={{ color: '#fff' }}>
                {liveBoxes.filter(b => b.resolved).length}/{liveBoxes.length} 框已对齐 DOM ·
                iframe 滚动时画框自动跟随
              </Text>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
