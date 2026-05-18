import { useState } from 'react'

export default function EmailCapture({ onContinue }) {
  const [email, setEmail] = useState('')

  return (
    <div style={{
      minHeight: '100vh',
      background: '#F5F7FB',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '48px 28px 40px',
    }}>
      {/* Brand wordmark */}
      <p style={{
        fontFamily: 'Playfair Display, serif',
        fontStyle: 'italic',
        fontSize: 28,
        fontWeight: 400,
        color: '#0057FF',
        marginBottom: 36,
        letterSpacing: '-0.01em',
      }}>
        horizon
      </p>

      {/* Headline */}
      <h1 style={{
        fontFamily: 'Playfair Display, serif',
        fontSize: 40,
        fontWeight: 700,
        color: '#0D0D0D',
        textAlign: 'center',
        lineHeight: 1.15,
        marginBottom: 18,
      }}>
        Your portfolio<br />is ready.
      </h1>

      {/* Subheading */}
      <p style={{
        fontSize: 15,
        color: '#6B7280',
        textAlign: 'center',
        lineHeight: 1.65,
        marginBottom: 40,
        maxWidth: 310,
      }}>
        We're connecting real market data and live signals. Enter your email to be the first to know when Horizon goes fully live — and to save your portfolio.
      </p>

      {/* Email input */}
      <input
        type="email"
        inputMode="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="your@email.com"
        style={{
          width: '100%',
          padding: '16px 18px',
          fontSize: 16,
          fontFamily: 'DM Sans, sans-serif',
          color: '#0D0D0D',
          background: '#FFFFFF',
          border: '1.5px solid #E5E7EB',
          borderRadius: 14,
          outline: 'none',
          boxSizing: 'border-box',
          marginBottom: 14,
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => e.target.style.borderColor = '#0057FF'}
        onBlur={(e) => e.target.style.borderColor = '#E5E7EB'}
        onKeyDown={(e) => e.key === 'Enter' && onContinue(email || null)}
      />

      {/* CTA button */}
      <button
        onClick={() => onContinue(email || null)}
        style={{
          width: '100%',
          padding: '17px 0',
          borderRadius: 14,
          border: 'none',
          background: '#0057FF',
          color: '#fff',
          fontSize: 16,
          fontWeight: 600,
          fontFamily: 'DM Sans, sans-serif',
          cursor: 'pointer',
          marginBottom: 14,
          transition: 'transform 0.1s',
        }}
        onMouseDown={(e) => { e.currentTarget.style.transform = 'scale(0.98)' }}
        onMouseUp={(e) => { e.currentTarget.style.transform = 'scale(1)' }}
      >
        See My Portfolio
      </button>

      {/* No spam */}
      <p style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 18 }}>
        No spam. Unsubscribe anytime.
      </p>

      {/* Skip */}
      <button
        onClick={() => onContinue(null)}
        style={{
          background: 'none',
          border: 'none',
          fontSize: 14,
          color: '#9CA3AF',
          cursor: 'pointer',
          fontFamily: 'DM Sans, sans-serif',
          padding: '4px 0',
          textDecoration: 'underline',
          textDecorationColor: '#D1D5DB',
        }}
      >
        Skip for now
      </button>
    </div>
  )
}
