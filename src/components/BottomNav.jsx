const NAV_TABS = [
  {
    key: 'askai',
    label: 'Ask AI',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M4 10C4 6.69 6.69 4 10 4C13.31 4 16 6.69 16 10C16 13.31 13.31 16 10 16C8.6 16 7.3 15.56 6.24 14.8L4 16L4.8 13.76C4.04 12.7 3.6 11.4 3.6 10H4Z"
          stroke={active ? '#0057FF' : '#9CA3AF'} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="7.5" cy="10" r="0.8" fill={active ? '#0057FF' : '#9CA3AF'}/>
        <circle cx="10" cy="10" r="0.8" fill={active ? '#0057FF' : '#9CA3AF'}/>
        <circle cx="12.5" cy="10" r="0.8" fill={active ? '#0057FF' : '#9CA3AF'}/>
      </svg>
    ),
  },
  {
    key: 'portfolio',
    label: 'Portfolio',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="2" y="11" width="4" height="7" rx="1" fill={active ? '#0057FF' : '#9CA3AF'} />
        <rect x="8" y="7" width="4" height="11" rx="1" fill={active ? '#0057FF' : '#9CA3AF'} />
        <rect x="14" y="3" width="4" height="15" rx="1" fill={active ? '#0057FF' : '#9CA3AF'} />
      </svg>
    ),
  },
  {
    key: 'signals',
    label: 'Signals',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M2 10 L5 6 L8 13 L11 4 L14 10 L17 8" stroke={active ? '#0057FF' : '#9CA3AF'} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    key: 'alerts',
    label: 'Alerts',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 2.5 C7 2.5 4.5 5 4.5 8.5 L4.5 13 L3 14.5 H17 L15.5 13 L15.5 8.5 C15.5 5 13 2.5 10 2.5Z" stroke={active ? '#0057FF' : '#9CA3AF'} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M8 15.5 C8 16.6 8.9 17.5 10 17.5 C11.1 17.5 12 16.6 12 15.5" stroke={active ? '#0057FF' : '#9CA3AF'} strokeWidth="1.7" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    key: 'performance',
    label: 'Performance',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M3 15 L7.5 9.5 L11 12.5 L17 5" stroke={active ? '#0057FF' : '#9CA3AF'} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M13.5 5 H17 V8.5" stroke={active ? '#0057FF' : '#9CA3AF'} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
]

export default function BottomNav({ activeTab, onTabChange }) {
  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: '50%',
      transform: 'translateX(-50%)',
      width: '100%',
      maxWidth: 390,
      background: '#FFFFFF',
      borderTop: '1px solid #F0F0F0',
      display: 'flex',
      zIndex: 100,
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      {NAV_TABS.map((tab) => {
        const active = tab.key === activeTab
        return (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              padding: '10px 4px 12px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            {tab.icon(active)}
            <span style={{
              fontSize: 10,
              fontWeight: active ? 600 : 400,
              color: active ? '#0057FF' : '#9CA3AF',
              fontFamily: 'DM Sans, sans-serif',
              letterSpacing: '0.01em',
            }}>
              {tab.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}
