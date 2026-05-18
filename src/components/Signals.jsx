const SIGNALS = [
  {
    id: 'ai-cooling',
    tickers: 'VICR · CDNS · LSCC',
    name: 'AI Cooling Infrastructure',
    bucket: 'WAVE',
    risk: 'LOW-MED',
    desc: 'Every AI data center needs cooling systems to stop servers overheating. Demand is up 400% since 2023. Companies making this hardware are small, growing fast, and flying under Wall Street\'s radar.',
    upside: '+280%',
    downside: '-35%',
    checks: 4,
    total: 5,
  },
  {
    id: 'nuclear',
    tickers: 'SMR · CCJ · UEC',
    name: 'Small Nuclear Energy',
    bucket: 'WAVE',
    risk: 'LOW',
    desc: 'Every country that signed a net-zero target needs 24/7 clean power. Nuclear is the only option that runs constantly. Governments that swore off nuclear 20 years ago are reversing course fast.',
    upside: '+220%',
    downside: '-28%',
    checks: 5,
    total: 5,
  },
  {
    id: 'cerebras',
    tickers: 'CBRS',
    name: 'Cerebras Systems',
    bucket: 'FRONTIER',
    risk: 'HIGH',
    desc: 'Just went public. Makes AI chips faster than NVIDIA for certain tasks. Microsoft and government contracts already signed. High risk but real revenue and institutional backing.',
    upside: '+900%',
    downside: '-80%',
    checks: 4,
    total: 5,
  },
]

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
        <div
          key={i}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: i < checks ? '#0057FF' : '#E5E7EB',
            flexShrink: 0,
          }}
        />
      ))}
      <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 3, fontWeight: 400 }}>
        {checks} of {total} checks passed
      </span>
    </div>
  )
}

function SignalCard({ signal }) {
  const bucketStyle = BUCKET_STYLE[signal.bucket]
  const riskStyle = RISK_STYLE[signal.risk]

  return (
    <div style={{
      background: '#FFFFFF',
      borderRadius: 18,
      padding: '20px 20px 18px',
      marginBottom: 12,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      borderLeft: `3px solid ${bucketStyle.border}`,
    }}>
      {/* Ticker */}
      <p style={{
        fontSize: 12,
        color: '#9CA3AF',
        fontWeight: 500,
        letterSpacing: '0.03em',
        marginBottom: 8,
      }}>
        {signal.tickers}
      </p>

      {/* Name */}
      <p style={{
        fontSize: 20,
        fontWeight: 700,
        color: '#0D0D0D',
        lineHeight: 1.2,
        marginBottom: 12,
      }}>
        {signal.name}
      </p>

      {/* Badges */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
        <Badge label={signal.bucket} bg={bucketStyle.bg} color={bucketStyle.color} />
        <Badge label={`RISK: ${signal.risk}`} bg={riskStyle.bg} color={riskStyle.color} />
      </div>
      <p style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 14 }}>
        {BUCKET_SUBTITLE[signal.bucket]}
      </p>

      {/* Description */}
      <p style={{
        fontSize: 14,
        color: '#6B7280',
        lineHeight: 1.6,
        marginBottom: 16,
      }}>
        {signal.desc}
      </p>

      {/* Upside / Downside */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <div style={{
          flex: 1,
          background: '#F0FDF4',
          borderRadius: 12,
          padding: '12px 14px',
        }}>
          <p style={{ fontSize: 11, color: '#16A34A', fontWeight: 600, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Upside</p>
          <p style={{ fontSize: 22, fontWeight: 700, color: '#16A34A', fontFamily: 'Playfair Display, serif', lineHeight: 1 }}>
            {signal.upside}
          </p>
        </div>
        <div style={{
          flex: 1,
          background: '#FFF1F2',
          borderRadius: 12,
          padding: '12px 14px',
        }}>
          <p style={{ fontSize: 11, color: '#DC2626', fontWeight: 600, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Downside</p>
          <p style={{ fontSize: 22, fontWeight: 700, color: '#DC2626', fontFamily: 'Playfair Display, serif', lineHeight: 1 }}>
            {signal.downside}
          </p>
        </div>
      </div>

      {/* Check dots */}
      <CheckDots checks={signal.checks} total={signal.total} />
    </div>
  )
}

export default function Signals() {
  return (
    <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 88 }}>
      {/* Header */}
      <div style={{ padding: '56px 24px 8px' }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: '#0D0D0D', marginBottom: 4 }}>
          Signals
        </h1>
        <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 24 }}>
          Curated opportunities for your buckets
        </p>
      </div>

      {/* Cards */}
      <div style={{ padding: '0 16px' }}>
        {SIGNALS.map((signal) => (
          <SignalCard key={signal.id} signal={signal} />
        ))}
      </div>
    </div>
  )
}
