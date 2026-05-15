const ALERTS = [
  {
    id: 'goldman',
    dot: '#0057FF',
    title: 'Goldman just upgraded AI infrastructure',
    time: '2h ago',
    desc: 'Goldman Sachs raised their 12-month price target on data center stocks by 40%. This directly supports your Wave holding in AI Cooling Infrastructure.',
    tag: 'ANCHOR UPDATE',
    tagBg: '#EEF4FF',
    tagColor: '#0057FF',
  },
  {
    id: 'nuclear-etf',
    dot: '#10B981',
    title: 'New nuclear energy ETF just launched',
    time: '5h ago',
    desc: 'Uranium prices hit a 15-year high this week. A new ETF tracking small nuclear companies just launched on NYSE.',
    tag: 'WAVE SIGNAL',
    tagBg: '#FFFBEB',
    tagColor: '#92400E',
  },
  {
    id: 'space-ipo',
    dot: '#F59E0B',
    title: 'Space logistics startup filing for IPO',
    time: '1d ago',
    desc: 'A company that delivers satellites for other companies just filed S-1 paperwork — first step to going public. NASA and SpaceX are both clients.',
    tag: 'FRONTIER WATCH',
    tagBg: '#ECFDF5',
    tagColor: '#065F46',
  },
  {
    id: 'fed-rates',
    dot: '#0057FF',
    title: 'Fed held interest rates steady',
    time: '2d ago',
    desc: 'The Federal Reserve kept rates unchanged today. In plain English: borrowing stays the same price, which is good for growth stocks in your Anchor bucket.',
    tag: 'ANCHOR UPDATE',
    tagBg: '#EEF4FF',
    tagColor: '#0057FF',
  },
]

function AlertCard({ alert }) {
  return (
    <div style={{
      background: '#FFFFFF',
      borderRadius: 16,
      padding: '16px 18px',
      marginBottom: 10,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      display: 'flex',
      gap: 14,
    }}>
      {/* Colored dot */}
      <div style={{ paddingTop: 5, flexShrink: 0 }}>
        <div style={{ width: 9, height: 9, borderRadius: '50%', background: alert.dot }} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 6 }}>
          <p style={{ fontSize: 15, fontWeight: 700, color: '#0D0D0D', lineHeight: 1.3 }}>
            {alert.title}
          </p>
          <span style={{ fontSize: 12, color: '#9CA3AF', whiteSpace: 'nowrap', flexShrink: 0, marginTop: 2 }}>
            {alert.time}
          </span>
        </div>

        <p style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.6, marginBottom: 12 }}>
          {alert.desc}
        </p>

        <span style={{
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.04em',
          background: alert.tagBg,
          color: alert.tagColor,
          padding: '4px 10px',
          borderRadius: 99,
        }}>
          {alert.tag}
        </span>
      </div>
    </div>
  )
}

export default function Alerts() {
  return (
    <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 88 }}>
      <div style={{ padding: '56px 24px 8px' }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: '#0D0D0D', marginBottom: 4 }}>Alerts</h1>
        <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 24 }}>What's moving in your portfolio</p>
      </div>
      <div style={{ padding: '0 16px' }}>
        {ALERTS.map((alert) => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </div>
    </div>
  )
}
