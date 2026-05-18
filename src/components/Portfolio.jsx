import { useState } from 'react'

const ANNUAL_RETURN = 0.08
const YEARS = 10

function project(initial, monthly, years, rate) {
  const monthlyRate = rate / 12
  const months = years * 12
  const lumpSum = Number(initial || 0) * Math.pow(1 + monthlyRate, months)
  const recurringFV = Number(monthly || 0) * ((Math.pow(1 + monthlyRate, months) - 1) / monthlyRate)
  return Math.round(lumpSum + recurringFV)
}

function formatDollar(val) {
  const n = Number(val || 0)
  return `$${Math.round(n).toLocaleString('en-US')}`
}

const BUCKETS = [
  {
    key: 'anchor',
    label: 'The Anchor',
    subtitle: 'Proven long-term holdings',
    pct: 0.6,
    color: '#0057FF',
    desc: 'Global index funds & bonds. Steady, diversified, resilient.',
  },
  {
    key: 'wave',
    label: 'The Wave',
    subtitle: 'Emerging verified opportunities',
    pct: 0.3,
    color: '#F59E0B',
    desc: 'Sector ETFs & growth stocks. Riding momentum, managed risk.',
  },
  {
    key: 'frontier',
    label: 'The Frontier',
    subtitle: 'High risk high reward',
    pct: 0.1,
    color: '#10B981',
    desc: 'Emerging markets & crypto. High upside, high volatility.',
  },
]

const PROJ_ROWS = [
  { label: '1 Year',   years: 1 },
  { label: '5 Years',  years: 5 },
  { label: '10 Years', years: 10 },
]

function ProjectionTable({ initial, monthly }) {
  return (
    <div style={{ margin: '20px 16px 0', background: '#FFFFFF', borderRadius: 18, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
      {/* Header */}
      <div style={{ display: 'grid', gridTemplateColumns: '0.9fr 1fr 1fr', background: '#0057FF', padding: '12px 16px', gap: 4 }}>
        <div />
        <p style={{ fontSize: 10, fontWeight: 600, color: 'rgba(255,255,255,0.8)', textAlign: 'center', letterSpacing: '0.03em', lineHeight: 1.4 }}>
          Conservative{'\n'}5% / yr
        </p>
        <p style={{ fontSize: 10, fontWeight: 600, color: '#fff', textAlign: 'center', letterSpacing: '0.03em', lineHeight: 1.4 }}>
          Aggressive{'\n'}8% / yr
        </p>
      </div>
      {PROJ_ROWS.map((row, i) => (
        <div
          key={row.label}
          style={{
            display: 'grid',
            gridTemplateColumns: '0.9fr 1fr 1fr',
            padding: '14px 16px',
            borderTop: i === 0 ? 'none' : '1px solid #F5F5F5',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <p style={{ fontSize: 13, fontWeight: 600, color: '#0D0D0D' }}>{row.label}</p>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#6B7280', textAlign: 'center', fontFamily: 'Playfair Display, serif' }}>
            {formatDollar(project(initial, monthly, row.years, 0.05))}
          </p>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#0057FF', textAlign: 'center', fontFamily: 'Playfair Display, serif' }}>
            {formatDollar(project(initial, monthly, row.years, 0.08))}
          </p>
        </div>
      ))}
    </div>
  )
}

function BaseCard({ emergency, totalInitial }) {
  const needsBase = emergency === 'no' || emergency === 'partial'
  const baseAmount = needsBase ? Number(totalInitial || 0) * 0.2 : 0

  return (
    <div style={{ background: '#FFFFFF', borderRadius: 18, overflow: 'hidden', marginBottom: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
      <div style={{ height: 3, background: '#9CA3AF' }} />
      <div style={{ padding: '18px 20px' }}>
        <div style={{ marginBottom: 10 }}>
          <p style={{ fontSize: 15, fontWeight: 700, color: '#0D0D0D' }}>The Base</p>
          <p style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 2 }}>Emergency fund first. Everything else second.</p>
          {needsBase && <p style={{ fontSize: 12, color: '#6B7280' }}>20% of your amount</p>}
        </div>

        {!needsBase ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#F0FDF4', borderRadius: 12, padding: '12px 14px' }}>
            <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#10B981', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
                <path d="M1 4.5L4 7.5L10 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p style={{ fontSize: 13, color: '#065F46', lineHeight: 1.5 }}>
              Your emergency fund is covered. 100% deployed into your portfolio.
            </p>
          </div>
        ) : (
          <>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 14, lineHeight: 1.5 }}>
              High-yield savings. Your safety net before your growth engine. No risk, instant access.
            </p>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <div>
                <p style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Set aside</p>
                <p style={{ fontSize: 18, fontWeight: 700, color: '#0D0D0D', fontFamily: 'Playfair Display, serif' }}>
                  {formatDollar(baseAmount)}
                </p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Growth</p>
                <p style={{ fontSize: 12, fontWeight: 500, color: '#9CA3AF' }}>No risk · Instant access</p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function BucketCard({ bucket, initialAmount, monthlyAmount }) {
  const bucketInitial = Number(initialAmount || 0) * bucket.pct
  const bucketMonthly = Number(monthlyAmount || 0) * bucket.pct
  const projected = project(bucketInitial, bucketMonthly, YEARS, ANNUAL_RETURN)

  return (
    <div style={{
      background: '#FFFFFF',
      borderRadius: 18,
      overflow: 'hidden',
      marginBottom: 12,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    }}>
      <div style={{ height: 3, background: bucket.color }} />
      <div style={{ padding: '18px 20px' }}>
        <div style={{ marginBottom: 10 }}>
          <p style={{ fontSize: 15, fontWeight: 700, color: '#0D0D0D' }}>{bucket.label}</p>
          <p style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 2 }}>{bucket.subtitle}</p>
          <p style={{ fontSize: 12, color: '#6B7280' }}>{Math.round(bucket.pct * 100)}% of portfolio</p>
        </div>

        <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 14, lineHeight: 1.5 }}>{bucket.desc}</p>

        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div>
            <p style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Invested</p>
            <p style={{ fontSize: 18, fontWeight: 700, color: '#0D0D0D', fontFamily: 'Playfair Display, serif' }}>
              {formatDollar(bucketInitial)}
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>10yr projection</p>
            <p style={{ fontSize: 18, fontWeight: 700, color: bucket.color, fontFamily: 'Playfair Display, serif' }}>
              {formatDollar(projected)}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Portfolio({ answers, onEdit }) {
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const { initial, monthly, risk, emergency } = answers
  const totalInitial = Number(initial || 0)
  const needsBase = emergency === 'no' || emergency === 'partial'
  const investable = needsBase ? totalInitial * 0.8 : totalInitial
  const totalProjected = project(investable, monthly, YEARS, ANNUAL_RETURN)

  const riskLabel = { sell: 'Conservative', hold: 'Balanced', buy: 'Aggressive' }[risk] || 'Balanced'

  return (
    <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 88 }}>
      {/* Sample data banner */}
      {!bannerDismissed && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#0057FF',
          padding: '10px 16px',
          gap: 12,
        }}>
          <p style={{
            fontSize: 12,
            fontWeight: 500,
            color: '#fff',
            lineHeight: 1.4,
            flex: 1,
          }}>
            Sample data — real signals and live prices coming soon.
          </p>
          <button
            onClick={() => setBannerDismissed(true)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 4,
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: 0.7,
            }}
            aria-label="Dismiss"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 2L12 12M12 2L2 12" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      )}
      {/* Hero card */}
      <div style={{
        background: 'linear-gradient(135deg, #0057FF 0%, #003FBF 100%)',
        borderRadius: '0 0 28px 28px',
        padding: '52px 28px 44px',
        color: '#fff',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Decorative circles */}
        <div style={{ position: 'absolute', top: -50, right: -50, width: 180, height: 180, borderRadius: '50%', background: 'rgba(255,255,255,0.06)' }} />
        <div style={{ position: 'absolute', top: 30, right: 10, width: 90, height: 90, borderRadius: '50%', background: 'rgba(255,255,255,0.06)' }} />

        {/* Top row: Edit (left) + Risk badge (right) */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, position: 'relative' }}>
          <button
            onClick={onEdit}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: 'rgba(255,255,255,0.15)',
              border: 'none',
              borderRadius: 8,
              padding: '6px 12px',
              color: '#fff',
              fontSize: 13,
              fontWeight: 500,
              fontFamily: 'DM Sans, sans-serif',
              cursor: 'pointer',
              letterSpacing: '0.01em',
            }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M8.5 1.5 L10.5 3.5 L4 10 L1.5 10.5 L2 8 L8.5 1.5Z" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Edit
          </button>
          <span style={{
            fontSize: 11,
            fontWeight: 500,
            background: 'rgba(255,255,255,0.15)',
            padding: '5px 12px',
            borderRadius: 99,
            letterSpacing: '0.04em',
            opacity: 0.9,
          }}>
            {riskLabel}
          </span>
        </div>

        {/* Logo row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 36 }}>
          <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="16" fill="rgba(255,255,255,0.2)" />
            <path d="M8 22 L16 10 L24 22" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
          <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.02em', opacity: 0.85 }}>Horizon</span>
        </div>

        {/* Total invested — secondary number */}
        <p style={{ fontSize: 12, opacity: 0.65, marginBottom: 6, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Total invested today
        </p>
        <p style={{ fontSize: 32, fontWeight: 700, fontFamily: 'Playfair Display, serif', lineHeight: 1, marginBottom: 6 }}>
          {formatDollar(investable)}
        </p>
        {Number(monthly) > 0 && (
          <p style={{ fontSize: 13, opacity: 0.65, marginBottom: 0 }}>+ {formatDollar(monthly)} / month</p>
        )}

        <div style={{ height: 1, background: 'rgba(255,255,255,0.15)', margin: '28px 0' }} />

        {/* 10-year projection — hero number */}
        <p style={{ fontSize: 12, opacity: 0.65, marginBottom: 8, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          10-year projection
        </p>
        <p style={{ fontSize: 52, fontWeight: 700, fontFamily: 'Playfair Display, serif', lineHeight: 1, marginBottom: 10 }}>
          {formatDollar(totalProjected)}
        </p>
        <p style={{ fontSize: 13, opacity: 0.65 }}>Estimated at +8% / yr</p>
      </div>

      <ProjectionTable initial={investable} monthly={monthly} />

      {/* Buckets */}
      <div style={{ padding: '24px 16px 0' }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: '#6B7280', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '0.06em', paddingLeft: 4 }}>
          Your buckets
        </p>
        <BaseCard emergency={emergency} totalInitial={totalInitial} />
        {BUCKETS.map((bucket) => (
          <BucketCard
            key={bucket.key}
            bucket={bucket}
            initialAmount={investable}
            monthlyAmount={monthly}
          />
        ))}
      </div>

      {/* Disclaimer */}
      <p style={{ fontSize: 11, color: '#9CA3AF', textAlign: 'center', padding: '16px 24px 0', lineHeight: 1.6 }}>
        Projections assume 8% annual return and are for illustrative purposes only. Past performance does not guarantee future results.
      </p>

    </div>
  )
}
