import { useEffect, useState } from 'react'

const DOTS = ['.', '..', '...']

export default function Loading() {
  const [dotIdx, setDotIdx] = useState(0)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const dotTimer = setInterval(() => setDotIdx((i) => (i + 1) % DOTS.length), 500)
    return () => clearInterval(dotTimer)
  }, [])

  useEffect(() => {
    const start = Date.now()
    const duration = 1900
    const raf = () => {
      const elapsed = Date.now() - start
      setProgress(Math.min(elapsed / duration, 1))
      if (elapsed < duration) requestAnimationFrame(raf)
    }
    requestAnimationFrame(raf)
  }, [])

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '0 32px',
      background: '#F5F7FB',
    }}>
      {/* Animated logo */}
      <div style={{ marginBottom: 32, animation: 'pulse 1.5s ease-in-out infinite' }}>
        <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
          <circle cx="26" cy="26" r="26" fill="#0057FF" opacity={0.12} />
          <circle cx="26" cy="26" r="18" fill="#0057FF" opacity={0.2} />
          <circle cx="26" cy="26" r="10" fill="#0057FF" />
          <path d="M19 34 L26 20 L33 34" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      </div>

      <h2 style={{
        fontSize: 22,
        fontWeight: 700,
        color: '#0D0D0D',
        marginBottom: 8,
        fontFamily: 'DM Sans, sans-serif',
      }}>
        Building your portfolio{DOTS[dotIdx]}
      </h2>
      <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 36, textAlign: 'center' }}>
        Analysing your risk profile and goals
      </p>

      {/* Progress bar */}
      <div style={{
        width: '100%',
        maxWidth: 280,
        height: 4,
        background: '#E5E7EB',
        borderRadius: 99,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${progress * 100}%`,
          background: '#0057FF',
          borderRadius: 99,
          transition: 'width 0.05s linear',
        }} />
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.08); }
        }
      `}</style>
    </div>
  )
}
