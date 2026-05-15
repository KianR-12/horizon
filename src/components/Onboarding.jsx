import { useState } from 'react'

const TOTAL = 3

function ProgressBar({ step }) {
  return (
    <div style={{ display: 'flex', gap: 6, marginBottom: 36 }}>
      {Array.from({ length: TOTAL }).map((_, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: 3,
            borderRadius: 99,
            background: i < step ? '#0057FF' : '#E5E7EB',
            transition: 'background 0.3s ease',
          }}
        />
      ))}
    </div>
  )
}

function StepLabel({ step }) {
  return (
    <p style={{ fontSize: 13, fontWeight: 500, color: '#6B7280', marginBottom: 12, letterSpacing: '0.04em' }}>
      STEP {step} OF {TOTAL}
    </p>
  )
}

function DollarInput({ value, onChange, placeholder }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      background: '#F9FAFB',
      border: '1.5px solid #E5E7EB',
      borderRadius: 14,
      padding: '0 16px',
      transition: 'border-color 0.2s',
    }}
    onFocus={(e) => e.currentTarget.style.borderColor = '#0057FF'}
    onBlur={(e) => e.currentTarget.style.borderColor = '#E5E7EB'}
    >
      <span style={{ fontSize: 22, fontWeight: 500, color: '#9CA3AF', marginRight: 6, fontFamily: 'DM Sans, sans-serif' }}>$</span>
      <input
        type="number"
        inputMode="decimal"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          flex: 1,
          border: 'none',
          background: 'transparent',
          fontSize: 22,
          fontWeight: 600,
          fontFamily: 'DM Sans, sans-serif',
          color: '#0D0D0D',
          padding: '18px 0',
          outline: 'none',
          width: '100%',
        }}
      />
    </div>
  )
}

const RISK_OPTIONS = [
  { key: 'sell', label: 'Sell', desc: 'Get out before it drops more' },
  { key: 'hold', label: 'Hold', desc: 'Stay the course, ride it out' },
  { key: 'buy', label: 'Buy More', desc: 'Opportunity to get in cheaper' },
]

function RiskIcon({ optKey, isSelected }) {
  const color = isSelected ? '#0057FF' : '#9CA3AF'
  const paths = {
    sell: <path d="M8 3v9M3.5 8.5l4.5 4 4.5-4" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
    hold: <path d="M3 6.5h10M3 9.5h10" stroke={color} strokeWidth="1.8" strokeLinecap="round" />,
    buy:  <path d="M8 13V4M3.5 7.5l4.5-4 4.5 4" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
  }
  return (
    <div style={{
      width: 38,
      height: 38,
      borderRadius: 10,
      background: isSelected ? '#DBEAFF' : '#F3F4F6',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      transition: 'background 0.18s ease',
    }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">{paths[optKey]}</svg>
    </div>
  )
}

function RiskButton({ option, selected, onClick }) {
  const isSelected = selected === option.key
  return (
    <button
      onClick={() => onClick(option.key)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        width: '100%',
        padding: '16px 18px',
        borderRadius: 14,
        border: `1.5px solid ${isSelected ? '#0057FF' : '#E5E7EB'}`,
        background: isSelected ? '#EEF4FF' : '#F9FAFB',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'all 0.18s ease',
        marginBottom: 12,
      }}
    >
      <RiskIcon optKey={option.key} isSelected={isSelected} />
      <div>
        <p style={{ fontSize: 15, fontWeight: 600, color: isSelected ? '#0057FF' : '#0D0D0D', marginBottom: 2 }}>
          {option.label}
        </p>
        <p style={{ fontSize: 13, color: '#6B7280', fontWeight: 400 }}>{option.desc}</p>
      </div>
      {isSelected && (
        <div style={{ marginLeft: 'auto', width: 20, height: 20, borderRadius: '50%', background: '#0057FF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      )}
    </button>
  )
}

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(1)
  const [initial, setInitial] = useState('')
  const [monthly, setMonthly] = useState('')
  const [risk, setRisk] = useState(null)

  function canContinue() {
    if (step === 1) return initial !== '' && Number(initial) >= 0
    if (step === 2) return monthly !== '' && Number(monthly) >= 0
    if (step === 3) return risk !== null
    return false
  }

  function handleNext() {
    if (step < TOTAL) {
      setStep(step + 1)
    } else {
      onComplete({ initial, monthly, risk })
    }
  }

  return (
    <div style={{ padding: '56px 24px 32px', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Logo */}
      <div style={{ marginBottom: 40 }}>
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <circle cx="16" cy="16" r="16" fill="#0057FF" />
          <path d="M8 22 L16 10 L24 22" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      </div>

      <ProgressBar step={step} />
      <StepLabel step={step} />

      <div style={{ flex: 1 }}>
        {step === 1 && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.3, marginBottom: 8, color: '#0D0D0D' }}>
              How much do you have available to invest right now?
            </h2>
            <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 28 }}>This is your starting point — even $50 counts.</p>
            <DollarInput value={initial} onChange={setInitial} placeholder="0" />
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.3, marginBottom: 8, color: '#0D0D0D' }}>
              How much can you add every month?
            </h2>
            <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 28 }}>Regular contributions make the biggest difference over time.</p>
            <DollarInput value={monthly} onChange={setMonthly} placeholder="0" />
          </div>
        )}

        {step === 3 && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.3, marginBottom: 8, color: '#0D0D0D' }}>
              If your money dropped 30% tomorrow, what would you do?
            </h2>
            <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 28 }}>Be honest — this shapes how we build your portfolio.</p>
            {RISK_OPTIONS.map((opt) => (
              <RiskButton key={opt.key} option={opt} selected={risk} onClick={setRisk} />
            ))}
          </div>
        )}
      </div>

      <button
        onClick={handleNext}
        disabled={!canContinue()}
        style={{
          width: '100%',
          padding: '17px 0',
          borderRadius: 14,
          border: 'none',
          background: canContinue() ? '#0057FF' : '#C7D7FF',
          color: '#fff',
          fontSize: 16,
          fontWeight: 600,
          fontFamily: 'DM Sans, sans-serif',
          cursor: canContinue() ? 'pointer' : 'not-allowed',
          transition: 'background 0.2s, transform 0.1s',
          marginTop: 24,
        }}
        onMouseDown={(e) => { if (canContinue()) e.currentTarget.style.transform = 'scale(0.98)' }}
        onMouseUp={(e) => { e.currentTarget.style.transform = 'scale(1)' }}
      >
        {step === TOTAL ? 'Build my portfolio' : 'Continue'}
      </button>
    </div>
  )
}
