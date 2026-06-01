import { fetchQuotes } from './stockApi.js'

const API_KEY  = import.meta.env.VITE_GROQ_API_KEY
const ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
const MODEL    = 'llama-3.1-8b-instant'

const SYSTEM_PROMPT = `You are Horizon AI, a friendly personal finance assistant built into the Horizon investing app. You help young investors understand their portfolio, explain financial concepts in plain English, and answer questions about investing. You are speaking to someone who is new to investing, likely between 18-25 years old. Always be encouraging, clear, and never use jargon without explaining it. Never recommend specific stocks to buy or sell — instead explain concepts and help users understand their options. Keep answers to 3 sentences maximum. Be conversational and encouraging.

You have access to a real-time stock price tool. Whenever a user asks about a stock price, percentage change, or how a specific ticker is doing today, always use the get_stock_price tool to fetch the latest data before answering. Never guess or make up prices.`

// ─── Tool definition ────────────────────────────────────────────────────────

const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'get_stock_price',
      description: 'Fetch the real-time price, change amount, and percentage change for a stock ticker. Use this whenever the user asks about a stock price or how a specific ticker is performing today.',
      parameters: {
        type: 'object',
        properties: {
          ticker: {
            type: 'string',
            description: 'The stock ticker symbol, e.g. "AAPL", "TSLA", "SPY", "NVDA"',
          },
        },
        required: ['ticker'],
      },
    },
  },
]

// ─── Tool executor ──────────────────────────────────────────────────────────

async function executeGetStockPrice(ticker) {
  const symbol = ticker.trim().toUpperCase()
  try {
    const quotes = await fetchQuotes([symbol])
    const q = quotes[symbol]
    if (!q || q.price === 0) {
      return { error: `Could not find ticker ${symbol}. Please check the symbol is correct.` }
    }
    const direction = q.change >= 0 ? 'up' : 'down'
    return {
      ticker:        symbol,
      price:         q.price,
      change:        q.change,
      changePercent: q.changePercent,
      direction,
      summary: `${symbol} is trading at $${q.price.toFixed(2)}, ${direction} ${Math.abs(q.changePercent).toFixed(2)}% ($${Math.abs(q.change).toFixed(2)}) today.`,
    }
  } catch {
    return { error: `Could not fetch data for ${symbol}. Try checking the symbol is correct.` }
  }
}

async function dispatchToolCall(name, argsJson) {
  try {
    const args = JSON.parse(argsJson)
    if (name === 'get_stock_price') {
      return await executeGetStockPrice(args.ticker)
    }
    return { error: `Unknown tool: ${name}` }
  } catch {
    return { error: 'Failed to parse tool arguments.' }
  }
}

// ─── System prompt builder ──────────────────────────────────────────────────

export function buildSystemPrompt(portfolioContext) {
  const { initial, monthly, risk, emergency } = portfolioContext
  const riskLabel  = { sell: 'Conservative', hold: 'Balanced', buy: 'Aggressive' }[risk] || 'Balanced'
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

// ─── Main send function ─────────────────────────────────────────────────────

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

  // ── Round 1: initial request with tools available ──────────────────────────
  const res1 = await fetch(ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model:       MODEL,
      messages,
      tools:       TOOLS,
      tool_choice: 'auto',
      temperature: 0.7,
      max_tokens:  300,
    }),
  })

  if (!res1.ok) {
    const err = await res1.text()
    throw new Error(`Groq API error ${res1.status}: ${err}`)
  }

  const data1   = await res1.json()
  const choice1 = data1.choices[0]

  // ── No tool call — return the direct answer ────────────────────────────────
  if (choice1.finish_reason !== 'tool_calls') {
    return choice1.message.content
  }

  // ── Round 2: execute each tool call, send results back ────────────────────
  const assistantMsg = choice1.message  // contains tool_calls array

  // Execute all tool calls (model may request multiple in one turn)
  const toolResultMsgs = await Promise.all(
    assistantMsg.tool_calls.map(async (tc) => {
      const result = await dispatchToolCall(tc.function.name, tc.function.arguments)
      return {
        role:         'tool',
        tool_call_id: tc.id,
        content:      JSON.stringify(result),
      }
    })
  )

  const messages2 = [
    ...messages,
    assistantMsg,        // assistant message with tool_calls
    ...toolResultMsgs,   // one tool result per call
  ]

  const res2 = await fetch(ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model:       MODEL,
      messages:    messages2,
      temperature: 0.7,
      max_tokens:  300,
    }),
  })

  if (!res2.ok) {
    const err = await res2.text()
    throw new Error(`Groq API error ${res2.status}: ${err}`)
  }

  const data2 = await res2.json()
  return data2.choices[0].message.content
}
