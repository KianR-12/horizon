const API_KEY  = import.meta.env.VITE_GROQ_API_KEY
const ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
const MODEL    = 'llama-3.1-8b-instant'

const SYSTEM_PROMPT = `You are Horizon AI, a friendly personal finance assistant built into the Horizon investing app. You help young investors understand their portfolio, explain financial concepts in plain English, and answer questions about investing. You are speaking to someone who is new to investing, likely between 18-25 years old. Always be encouraging, clear, and never use jargon without explaining it. Never recommend specific stocks to buy or sell — instead explain concepts and help users understand their options. Keep answers to 3 sentences maximum. Be conversational and encouraging.`

export function buildSystemPrompt(portfolioContext) {
  const { initial, monthly, risk, emergency, buckets } = portfolioContext
  const riskLabel = { sell: 'Conservative', hold: 'Balanced', buy: 'Aggressive' }[risk] || 'Balanced'
  const investable = emergency === 'no' || emergency === 'partial'
    ? Math.max(0, Number(initial || 0) - 1000)
    : Number(initial || 0)

  const contextLines = [
    `The user's portfolio context:`,
    `- Initial invested amount: $${Number(initial || 0).toLocaleString()}`,
    `- Monthly contribution: $${Number(monthly || 0).toLocaleString()}/month`,
    `- Risk tolerance: ${riskLabel}`,
    `- Emergency fund status: ${emergency === 'yes' ? 'Fully covered (invested 100%)' : emergency === 'partial' ? 'Partial — $1,000 held back as base' : 'None — $1,000 held back as base'}`,
    `- Portfolio split: Anchor (index funds/bonds) 60%, Wave (sector ETFs/growth) 30%, Frontier (emerging/crypto) 10%`,
    `- Anchor bucket: $${Math.round(investable * 0.6).toLocaleString()}`,
    `- Wave bucket: $${Math.round(investable * 0.3).toLocaleString()}`,
    `- Frontier bucket: $${Math.round(investable * 0.1).toLocaleString()}`,
  ]

  return `${SYSTEM_PROMPT}\n\n${contextLines.join('\n')}`
}

export async function sendMessage(userMessage, portfolioContext, conversationHistory = []) {
  if (!API_KEY) {
    throw new Error('VITE_GROQ_API_KEY is not set. Add it to your .env.local file.')
  }

  const systemPrompt = buildSystemPrompt(portfolioContext)

  const messages = [
    { role: 'system', content: systemPrompt },
    ...conversationHistory,
    { role: 'user', content: userMessage },
  ]

  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: MODEL,
      messages,
      temperature: 0.7,
      max_tokens: 300,
    }),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`Groq API error ${res.status}: ${err}`)
  }

  const data = await res.json()
  return data.choices[0].message.content
}
