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
    pct: 0.6,
    color: '#0057FF',
    desc: 'Global index funds & bonds. Steady, diversified, resilient.',
  },
  {
    key: 'wave',
    label: 'The Wave',
    pct: 0.3,
    color: '#F59E0B',
    desc: 'Sector ETFs & growth stocks. Riding momentum, managed risk.',
  },
  {
    key: 'frontier',
    label: 'The Frontier',
    pct: 0.1,
    color: '#10B981',
    desc: 'Emerging markets & crypto. High upside, high volatility.',
  },
]

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
  const { initial, monthly, risk } = answers
  const totalProjected = project(initial, monthly, YEARS, ANNUAL_RETURN)
  const totalInvested = Number(initial || 0)

  const riskLabel = { sell: 'Conservative', hold: 'Balanced', buy: 'Aggressive' }[risk] || 'Balanced'

  return (
    <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 88 }}>
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
          {formatDollar(totalInvested)}
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

      {/* Buckets */}
      <div style={{ padding: '24px 16px 0' }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: '#6B7280', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '0.06em', paddingLeft: 4 }}>
          Your buckets
        </p>
        {BUCKETS.map((bucket) => (
          <BucketCard
            key={bucket.key}
            bucket={bucket}
            initialAmount={initial}
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
