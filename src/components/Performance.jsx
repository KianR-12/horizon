import { useState } from 'react'

const PERIODS = ['1M', '3M', '6M', '1Y', 'All']

const PERIOD_RETURN = {
  '1M':  0.032,
  '3M':  0.087,
  '6M':  0.184,
  '1Y':  0.312,
  'All': 0.184,
}

// y values in SVG space (lower = higher on screen = better performance)
// x is computed evenly across 0–320
const CHART_Y = {
  '1M':  [78, 72, 76, 68, 62],
  '3M':  [82, 74, 67, 71, 58, 52],
  '6M':  [86, 78, 66, 72, 52, 40],
  '1Y':  [88, 82, 70, 76, 56, 38],
  'All': [86, 78, 66, 72, 52, 40],
}

const BUCKET_PERF = [
  { label: 'The Anchor',   alloc: 0.6, ret:  0.112, retStr: '+11.2%', color: '#0057FF' },
  { label: 'The Wave',     alloc: 0.3, ret:  0.348, retStr: '+34.8%', color: '#F59E0B' },
  { label: 'The Frontier', alloc: 0.1, ret: -0.124, retStr: '-12.4%', color: '#EF4444' },
]
const MAX_ABS_RET = 0.348

function formatDollar(val) {
  return `$${Math.round(Number(val || 0)).toLocaleString('en-US')}`
}

function formatGain(val) {
  const n = Math.round(Number(val || 0))
  return `${n >= 0 ? '+' : ''}$${Math.abs(n).toLocaleString('en-US')}`
}

function smoothPath(pts) {
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1]
    const [x1, y1] = pts[i]
    const cx = (x0 + x1) / 2
    d += ` C ${cx} ${y0} ${cx} ${y1} ${x1} ${y1}`
  }
  return d
}

function LineChart({ period }) {
  const yVals = CHART_Y[period] || CHART_Y['6M']
  const points = yVals.map((y, i) => [
    Math.round((i / (yVals.length - 1)) * 320),
    y,
  ])
  const last = points[points.length - 1]
  const linePath = smoothPath(points)
  const fillPath = `${linePath} L ${last[0]} 110 L 0 110 Z`

  return (
    <svg
      viewBox="0 0 320 110"
      style={{ width: '100%', height: 110, display: 'block' }}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="perfGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0057FF" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#0057FF" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[28, 56, 84].map((y) => (
        <line key={y} x1="0" y1={y} x2="320" y2={y} stroke="#F3F4F6" strokeWidth="1" />
      ))}
      <path d={fillPath} fill="url(#perfGrad)" />
      <path d={linePath} stroke="#0057FF" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="5" fill="#0057FF" />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill="white" />
    </svg>
  )
}

function BucketBar({ bucket, initial }) {
  const barWidth = (Math.abs(bucket.ret) / MAX_ABS_RET) * 100
  const barColor = bucket.ret >= 0 ? bucket.color : '#EF4444'
  const retColor = bucket.ret >= 0 ? bucket.color : '#EF4444'

  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 7 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#0D0D0D' }}>{bucket.label}</span>
          {initial > 0 && (
            <span style={{ fontSize: 12, color: '#9CA3AF' }}>{formatDollar(initial * bucket.alloc)}</span>
          )}
        </div>
        <span style={{ fontSize: 14, fontWeight: 700, color: retColor }}>{bucket.retStr}</span>
      </div>
      <div style={{ height: 6, background: '#F3F4F6', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${barWidth}%`,
          background: barColor,
          borderRadius: 99,
        }} />
      </div>
    </div>
  )
}

function InstinctScore() {
  const score = 4
  const total = 6
  const stats = [
    { label: 'Win Rate',   value: '67%' },
    { label: 'Avg Return', value: '+22.4%' },
    { label: 'Best Pick',  value: 'SMR +52%' },
  ]

  return (
    <div style={{
      background: '#FFFFFF',
      borderRadius: 18,
      padding: '20px',
      marginBottom: 12,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <p style={{ fontSize: 12, color: '#9CA3AF', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
            Instinct Score
          </p>
          <p style={{ fontSize: 34, fontWeight: 700, color: '#0D0D0D', fontFamily: 'Playfair Display, serif', lineHeight: 1 }}>
            {score}<span style={{ fontSize: 20, color: '#9CA3AF', fontWeight: 400 }}>/{total}</span>
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {Array.from({ length: total }).map((_, i) => (
            <div key={i} style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: i < score ? '#0057FF' : '#E5E7EB',
            }} />
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', borderTop: '1px solid #F5F5F5', paddingTop: 16 }}>
        {stats.map((stat, i) => (
          <div key={stat.label} style={{
            flex: 1,
            paddingLeft: i > 0 ? 14 : 0,
            paddingRight: i < stats.length - 1 ? 14 : 0,
            borderLeft: i > 0 ? '1px solid #F0F0F0' : 'none',
          }}>
            <p style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 3 }}>
              {stat.label}
            </p>
            <p style={{ fontSize: 14, fontWeight: 700, color: '#0D0D0D' }}>{stat.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function WhatYouMissed() {
  return (
    <div style={{
      background: '#FFFFFF',
      borderRadius: 18,
      padding: '20px',
      marginBottom: 12,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    }}>
      <p style={{ fontSize: 12, color: '#9CA3AF', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 14 }}>
        What you missed
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 18, fontWeight: 700, color: '#0D0D0D', marginBottom: 5 }}>PLTR</p>
          <p style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.6 }}>
            You saw this Frontier signal 6 months ago but didn't act. Palantir has returned +44.2% since.
          </p>
        </div>
        <div style={{
          background: '#F0FDF4',
          borderRadius: 12,
          padding: '12px 14px',
          textAlign: 'center',
          flexShrink: 0,
        }}>
          <p style={{ fontSize: 10, color: '#16A34A', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 3 }}>
            Would have been
          </p>
          <p style={{ fontSize: 22, fontWeight: 700, color: '#16A34A', fontFamily: 'Playfair Display, serif', lineHeight: 1 }}>
            +44.2%
          </p>
        </div>
      </div>
    </div>
  )
}

export default function Performance({ answers }) {
  const [period, setPeriod] = useState('6M')
  const initial = Number(answers?.initial || 0)
  const ret = PERIOD_RETURN[period]
  const currentValue = initial * (1 + ret)
  const gained = currentValue - initial

  return (
    <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 88 }}>
      {/* Hero card */}
      <div style={{
        background: 'linear-gradient(135deg, #0057FF 0%, #003FBF 100%)',
        borderRadius: '0 0 28px 28px',
        padding: '52px 28px 36px',
        color: '#fff',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{ position: 'absolute', top: -50, right: -50, width: 180, height: 180, borderRadius: '50%', background: 'rgba(255,255,255,0.06)' }} />
        <div style={{ position: 'absolute', top: 30, right: 10, width: 90, height: 90, borderRadius: '50%', background: 'rgba(255,255,255,0.06)' }} />

        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 32 }}>
          <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="16" fill="rgba(255,255,255,0.2)" />
            <path d="M8 22 L16 10 L24 22" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
          <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.02em', opacity: 0.85 }}>Horizon</span>
        </div>

        {/* Return */}
        <p style={{ fontSize: 12, opacity: 0.65, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
          Total Return · {period}
        </p>
        <p style={{ fontSize: 52, fontWeight: 700, fontFamily: 'Playfair Display, serif', lineHeight: 1, marginBottom: 28 }}>
          {ret >= 0 ? '+' : ''}{(ret * 100).toFixed(1)}%
        </p>

        <div style={{ height: 1, background: 'rgba(255,255,255,0.15)', marginBottom: 24 }} />

        {/* Three stats */}
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          {[
            { label: 'Invested',      value: formatDollar(initial),      align: 'left' },
            { label: 'Current Value', value: formatDollar(currentValue),  align: 'center' },
            { label: 'Gained',        value: formatGain(gained),          align: 'right' },
          ].map((stat) => (
            <div key={stat.label} style={{ textAlign: stat.align }}>
              <p style={{ fontSize: 11, opacity: 0.6, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                {stat.label}
              </p>
              <p style={{ fontSize: 16, fontWeight: 700, fontFamily: 'Playfair Display, serif' }}>{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: '20px 16px 0' }}>
        {/* Chart card */}
        <div style={{
          background: '#FFFFFF',
          borderRadius: 18,
          padding: '20px 20px 16px',
          marginBottom: 12,
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}>
          {/* Period selector */}
          <div style={{
            display: 'flex',
            gap: 4,
            background: '#F5F7FB',
            borderRadius: 10,
            padding: 4,
            marginBottom: 20,
          }}>
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                style={{
                  flex: 1,
                  padding: '7px 0',
                  border: 'none',
                  borderRadius: 7,
                  background: period === p ? '#0057FF' : 'transparent',
                  color: period === p ? '#fff' : '#6B7280',
                  fontSize: 12,
                  fontWeight: period === p ? 600 : 400,
                  fontFamily: 'DM Sans, sans-serif',
                  cursor: 'pointer',
                  transition: 'background 0.15s ease, color 0.15s ease',
                }}
              >
                {p}
              </button>
            ))}
          </div>

          <LineChart period={period} />
        </div>

        {/* Bucket performance */}
        <div style={{
          background: '#FFFFFF',
          borderRadius: 18,
          padding: '20px',
          marginBottom: 12,
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: '#9CA3AF', marginBottom: 18, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Bucket Performance
          </p>
          {BUCKET_PERF.map((bucket) => (
            <BucketBar key={bucket.label} bucket={bucket} initial={initial} />
          ))}
        </div>

        <InstinctScore />
        <WhatYouMissed />
      </div>
    </div>
  )
}
