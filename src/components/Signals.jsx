import { useState, useEffect } from 'react'
import { fetchQuotes } from '../services/stockApi.js'

const NOW = Date.now()

const SIGNALS = [
  {
    id: 'ai-cooling',
    name: 'AI Cooling Infrastructure',
    tickerKeys: ['VICR', 'CDNS', 'LSCC'],
    bucket: 'WAVE',
    risk: 'LOW-MED',
    isNew: true,
    flaggedAt: NOW - 2 * 60 * 60 * 1000,
    desc: "Every AI data center needs cooling systems to stop servers overheating. Demand is up 400% since 2023. Companies making this hardware are small, growing fast, and flying under Wall Street's radar.",
    upside: '+280%',
    upsideNum: 280,
    downside: '-35%',
    checks: 4,
    total: 5,
  },
  {
    id: 'nuclear',
    name: 'Small Nuclear Energy',
    tickerKeys: ['SMR', 'CCJ', 'UEC'],
    bucket: 'WAVE',
    risk: 'LOW',
    isNew: false,
    flaggedAt: NOW - 4 * 60 * 60 * 1000,
    desc: 'Every country that signed a net-zero target needs 24/7 clean power. Nuclear is the only option that runs constantly. Governments that swore off nuclear 20 years ago are reversing course fast.',
    upside: '+220%',
    upsideNum: 220,
    downside: '-28%',
    checks: 5,
    total: 5,
  },
  {
    id: 'cerebras',
    name: 'Cerebras Systems',
    tickerKeys: ['CBRS'],
    bucket: 'FRONTIER',
    risk: 'HIGH',
    isNew: false,
    flaggedAt: NOW - 6 * 60 * 60 * 1000,
    desc: 'Just went public. Makes AI chips faster than NVIDIA for certain tasks. Microsoft and government contracts already signed. High risk but real revenue and institutional backing.',
    upside: '+900%',
    upsideNum: 900,
    downside: '-80%',
    checks: 4,
    total: 5,
  },
]

const ALL_TICKERS = ['VICR', 'CDNS', 'LSCC', 'SMR', 'CCJ', 'UEC', 'CBRS']

const BUCKET_STYLE = {
  WAVE:     { bg: '#FFF8E7', color: '#92400E', border: '#D97706' },
  FRONTIER: { bg: '#ECFDF5', color: '#065F46', border: '#00A63E' },
}

const BUCKET_SUBTITLE = {
  WAVE:     'Emerging verified opportunities',
  FRONTIER: 'High risk high reward',
}

const RISK_STYLE = {
  'LOW':     { bg: '#ECFDF5', color: '#065F46' },
  'LOW-MED': { bg: '#FFFBEB', color: '#92400E' },
  'HIGH':    { bg: '#FEF2F2', color: '#B91C1C' },
}

function timeAgo(ts) {
  const mins = Math.floor((Date.now() - ts) / 60000)
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ago`
}

function Badge({ label, bg, color }) {
  return (
    <span style={{
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '0.04em',
      background: bg,
      color,
      padding: '4px 10px',
      borderRadius: 99,
    }}>
      {label}
    </span>
  )
}

function CheckDots({ checks, total }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: i < checks ? '#0057FF' : '#E5E7EB',
          flexShrink: 0,
        }} />
      ))}
      <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 3, fontWeight: 400 }}>
        {checks} of {total} checks passed
      </span>
    </div>
  )
}

function TickerLine({ tickerKeys, quotes, loading }) {
  if (loading) {
    return (
      <div style={{
        height: 14,
        width: '78%',
        background: '#EFEFEF',
        borderRadius: 4,
        marginBottom: 8,
        animation: 'shimmer 1.5s ease-in-out infinite',
      }} />
    )
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '2px 0', marginBottom: 8 }}>
      {tickerKeys.map((ticker, i) => {
        const q = quotes[ticker]
        const isUp = q && q.changePercent >= 0
        return (
          <span key={ticker} style={{ display: 'inline-flex', alignItems: 'center' }}>
            {i > 0 && (
              <span style={{ color: '#D1D5DB', margin: '0 6px', fontSize: 11 }}>·</span>
            )}
            <span style={{
              fontSize: 11,
              fontWeight: 600,
              color: '#9CA3AF',
              letterSpacing: '0.02em',
              marginRight: 4,
            }}>
              {ticker}
            </span>
            <span style={{
              fontSize: 11,
              color: '#6B7280',
              fontFamily: 'DM Mono, monospace',
              marginRight: 4,
            }}>
              {q ? `$${q.price.toFixed(2)}` : '—'}
            </span>
            {q && (
              <span style={{
                fontSize: 11,
                fontFamily: 'DM Mono, monospace',
                color: isUp ? '#00A63E' : '#D92B2B',
                fontWeight: 500,
              }}>
                {isUp ? '▲' : '▼'} {Math.abs(q.changePercent).toFixed(1)}%
              </span>
            )}
          </span>
        )
      })}
    </div>
  )
}

function SignalCard({ signal, quotes, loading, visible }) {
  const [displayedUpside, setDisplayedUpside] = useState(0)
  const bucketStyle = BUCKET_STYLE[signal.bucket]
  const riskStyle = RISK_STYLE[signal.risk]

  useEffect(() => {
    if (!visible) return
    const target = signal.upsideNum
    const duration = 800
    const startTime = performance.now()
    let raf

    function step(now) {
      const progress = Math.min((now - startTime) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayedUpside(Math.round(eased * target))
      if (progress < 1) raf = requestAnimationFrame(step)
    }

    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [visible]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{
      background: '#FFFFFF',
      borderRadius: 18,
      padding: '20px 20px 18px',
      marginBottom: 12,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      borderLeft: `3px solid ${bucketStyle.border}`,
      opacity: visible ? 1 : 0,
      transform: visible ? 'translateY(0)' : 'translateY(12px)',
      transition: 'opacity 0.4s ease, transform 0.4s ease',
    }}>
      {/* Live ticker prices */}
      <TickerLine tickerKeys={signal.tickerKeys} quotes={quotes} loading={loading} />

      {/* Name + NEW badge + timestamp */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 12 }}>
        <p style={{ fontSize: 20, fontWeight: 700, color: '#0D0D0D', lineHeight: 1.2, flex: 1 }}>
          {signal.name}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          {signal.isNew && (
            <span style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.06em',
              background: '#0057FF',
              color: '#fff',
              padding: '3px 8px',
              borderRadius: 99,
            }}>
              NEW
            </span>
          )}
          <span style={{ fontSize: 11, color: '#9CA3AF' }}>
            Flagged {timeAgo(signal.flaggedAt)}
          </span>
        </div>
      </div>

      {/* Bucket + risk badges */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
        <Badge label={signal.bucket} bg={bucketStyle.bg} color={bucketStyle.color} />
        <Badge label={`RISK: ${signal.risk}`} bg={riskStyle.bg} color={riskStyle.color} />
      </div>
      <p style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 14 }}>
        {BUCKET_SUBTITLE[signal.bucket]}
      </p>

      {/* Description */}
      <p style={{ fontSize: 14, color: '#6B7280', lineHeight: 1.6, marginBottom: 16 }}>
        {signal.desc}
      </p>

      {/* Upside / Downside */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <div style={{ flex: 1, background: '#F0FDF4', borderRadius: 12, padding: '12px 14px' }}>
          <p style={{ fontSize: 11, color: '#16A34A', fontWeight: 600, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Upside</p>
          <p style={{ fontSize: 22, fontWeight: 700, color: '#16A34A', fontFamily: 'Playfair Display, serif', lineHeight: 1 }}>
            +{displayedUpside}%
          </p>
        </div>
        <div style={{ flex: 1, background: '#FFF1F2', borderRadius: 12, padding: '12px 14px' }}>
          <p style={{ fontSize: 11, color: '#DC2626', fontWeight: 600, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Downside</p>
          <p style={{ fontSize: 22, fontWeight: 700, color: '#DC2626', fontFamily: 'Playfair Display, serif', lineHeight: 1 }}>
            {signal.downside}
          </p>
        </div>
      </div>

      <CheckDots checks={signal.checks} total={signal.total} />
    </div>
  )
}

export default function Signals() {
  const [quotes, setQuotes] = useState({})
  const [loading, setLoading] = useState(true)
  const [visible, setVisible] = useState(SIGNALS.map(() => false))

  useEffect(() => {
    fetchQuotes(ALL_TICKERS).then(data => {
      setQuotes(data)
      setLoading(false)
    })

    SIGNALS.forEach((_, i) => {
      setTimeout(() => {
        setVisible(prev => prev.map((v, j) => j === i ? true : v))
      }, 50 + i * 100)
    })
  }, [])

  return (
    <>
      <style>{`
        @keyframes shimmer {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
      <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 88 }}>
        <div style={{ padding: '56px 24px 8px' }}>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: '#0D0D0D', marginBottom: 4 }}>
            Signals
          </h1>
          <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 24 }}>
            Curated opportunities for your buckets
          </p>
        </div>
        <div style={{ padding: '0 16px' }}>
          {SIGNALS.map((signal, i) => (
            <SignalCard
              key={signal.id}
              signal={signal}
              quotes={quotes}
              loading={loading}
              visible={visible[i]}
            />
          ))}
        </div>
      </div>
    </>
  )
}
