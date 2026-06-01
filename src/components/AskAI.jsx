import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../services/groqApi.js'

const SUGGESTED = [
  'What is compound interest?',
  'Why is my Wave bucket riskier?',
  'What does the risk filter check?',
  'How is my 10-year projection calculated?',
]

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '10px 14px', background: '#F3F4F6', borderRadius: 18, borderBottomLeftRadius: 4, width: 58 }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: '#9CA3AF',
            display: 'inline-block',
            animation: 'bounce 1.2s ease-in-out infinite',
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 10,
    }}>
      <div style={{
        maxWidth: '78%',
        padding: '10px 14px',
        borderRadius: 18,
        borderBottomRightRadius: isUser ? 4 : 18,
        borderBottomLeftRadius: isUser ? 18 : 4,
        background: isUser ? '#0057FF' : '#F3F4F6',
        color: isUser ? '#FFFFFF' : '#0D0D0D',
        fontSize: 14,
        lineHeight: 1.55,
        fontFamily: 'DM Sans, sans-serif',
      }}>
        {msg.content}
      </div>
    </div>
  )
}

export default function AskAI({ answers }) {
  const [messages, setMessages]   = useState([])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const bottomRef                 = useRef(null)
  const inputRef                  = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function submit(text) {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg = { role: 'user', content: trimmed }
    const history = messages.map((m) => ({ role: m.role, content: m.content }))

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setError(null)
    setLoading(true)

    try {
      const reply = await sendMessage(trimmed, answers, history)
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(input)
    }
  }

  const showSuggestions = messages.length === 0

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      maxWidth: 390,
      background: '#FFFFFF',
      fontFamily: 'DM Sans, sans-serif',
    }}>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40%            { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>

      {/* Header */}
      <div style={{
        padding: '52px 20px 16px',
        background: '#FFFFFF',
        borderBottom: '1px solid #F0F0F0',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #0057FF 0%, #6C63FF 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 9C3 5.69 5.69 3 9 3C12.31 3 15 5.69 15 9C15 12.31 12.31 15 9 15C7.8 15 6.68 14.65 5.74 14.05L3 15L3.95 12.26C3.35 11.32 3 10.2 3 9Z" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <p style={{ fontSize: 15, fontWeight: 700, color: '#0D0D0D', margin: 0 }}>Horizon AI</p>
            <p style={{ fontSize: 12, color: '#10B981', margin: 0, fontWeight: 500 }}>● Online</p>
          </div>
        </div>
      </div>

      {/* Message thread */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px 16px 8px',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {showSuggestions && (
          <div style={{ textAlign: 'center', marginBottom: 24, marginTop: 8 }}>
            <p style={{ fontSize: 22, margin: '0 0 4px' }}>👋</p>
            <p style={{ fontSize: 15, fontWeight: 700, color: '#0D0D0D', margin: '0 0 4px' }}>Hi, I'm Horizon AI</p>
            <p style={{ fontSize: 13, color: '#6B7280', margin: 0, lineHeight: 1.5 }}>
              Ask me anything about your portfolio or investing basics.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <Message key={i} msg={msg} />
        ))}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 10 }}>
            <TypingIndicator />
          </div>
        )}

        {error && (
          <div style={{
            background: '#FEF2F2',
            border: '1px solid #FECACA',
            borderRadius: 10,
            padding: '10px 14px',
            fontSize: 13,
            color: '#DC2626',
            marginBottom: 8,
          }}>
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Suggested chips */}
      {showSuggestions && (
        <div style={{
          padding: '0 16px 10px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          flexShrink: 0,
        }}>
          {SUGGESTED.map((q) => (
            <button
              key={q}
              onClick={() => submit(q)}
              style={{
                padding: '7px 12px',
                borderRadius: 20,
                border: '1px solid #E5E7EB',
                background: '#F9FAFB',
                fontSize: 12,
                color: '#374151',
                cursor: 'pointer',
                fontFamily: 'DM Sans, sans-serif',
                fontWeight: 500,
                transition: 'background 0.15s',
              }}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div style={{
        padding: '10px 16px',
        paddingBottom: 'max(10px, env(safe-area-inset-bottom))',
        borderTop: '1px solid #F0F0F0',
        background: '#FFFFFF',
        flexShrink: 0,
        display: 'flex',
        gap: 10,
        alignItems: 'flex-end',
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask anything about your portfolio…"
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            border: '1px solid #E5E7EB',
            borderRadius: 22,
            padding: '10px 16px',
            fontSize: 14,
            fontFamily: 'DM Sans, sans-serif',
            color: '#0D0D0D',
            background: '#F9FAFB',
            outline: 'none',
            lineHeight: 1.5,
            maxHeight: 100,
            overflowY: 'auto',
          }}
        />
        <button
          onClick={() => submit(input)}
          disabled={!input.trim() || loading}
          style={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            background: input.trim() && !loading ? '#0057FF' : '#E5E7EB',
            border: 'none',
            cursor: input.trim() && !loading ? 'pointer' : 'default',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 8L14 8M14 8L9 3M14 8L9 13" stroke={input.trim() && !loading ? '#FFFFFF' : '#9CA3AF'} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  )
}
