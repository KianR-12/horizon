import { fetchQuotes } from './stockApi.js'

const API_KEY  = import.meta.env.VITE_GROQ_API_KEY
const ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
const MODEL    = 'llama-3.3-70b-versatile'

const SYSTEM_PROMPT = `You are Horizon AI, a friendly personal finance assistant built into the Horizon investing app. You help young investors understand their portfolio, explain financial concepts in plain English, and answer questions about investing. You are speaking to someone who is new to investing, likely between 18-25 years old. Always be encouraging, clear, and never use jargon without explaining it. Never recommend specific stocks to buy or sell — instead explain concepts and help users understand their options. Keep answers to 3 sentences maximum. Be conversational and encouraging.

You have access to a real-time stock price tool. Only use the get_stock_price tool when the user explicitly asks about a specific stock ticker symbol or asks for the current price of a named stock. For all general investing questions, portfolio questions, or concept explanations, answer directly without using any tools. Never call the tool speculatively or for questions that don't mention a specific ticker.`

// ─── Tool definition ────────────────────────────────────────────────────────

const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'get_stock_price',
      description: 'Fetch the real-time price and daily change for a specific stock ticker symbol. Only call this when the user explicitly mentions a ticker symbol (like AAPL, TSLA, SPY) or asks for the current price of a specific stock.',
      parameters: {
        type: 'object',
        properties: {
          ticker: {
            type: 'string',
            description: 'The stock ticker symbol in uppercase, e.g. "AAPL", "TSLA", "SPY", "NVDA"',
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
      return { error: `I couldn't find data for ${symbol} — please check the ticker symbol is correct.` }
    }
    const direction = q.change >= 0 ? 'up' : 'down'
    return {
      ticker:        symbol,
      price:         q.price,
      change:        q.change,
      changePercent: q.changePercent,
      direction,
      summary:       `${symbol} is at $${q.price.toFixed(2)}, ${direction} ${Math.abs(q.changePercent).toFixed(2)}% ($${Math.abs(q.change).toFixed(2)}) today.`,
    }
  } catch (e) {
    console.error('[groqApi] stock fetch failed:', e)
    return { error: `I couldn't find that ticker — try checking the symbol is correct.` }
  }
}

async function dispatchToolCall(name, argsJson) {
  try {
    const args = JSON.parse(argsJson)
    if (name === 'get_stock_price') {
      return await executeGetStockPrice(args.ticker)
    }
    return { error: `Unknown tool: ${name}` }
  } catch (e) {
    console.error('[groqApi] tool dispatch failed:', e)
    return { error: 'Tool call failed — please try again.' }
  }
}

// ─── Response cleaner ────────────────────────────────────────────────────────

function cleanResponse(text) {
  if (!text) return text
  return text
    .replace(/<tool_call>[\s\S]*?<\/tool_call>/gi, '')
    .replace(/```json[\s\S]*?```/gi, '')
    .replace(/\{[^{}]*"ticker"[^{}]*\}/gi, '')
    .replace(/\{[^{}]*"error"[^{}]*\}/gi, '')
    .replace(/\{[^{}]*"price"[^{}]*\}/gi, '')
    .trim()
}

// ─── Ticker extractor (for fallback path) ────────────────────────────────────
// Pulls uppercase 1-5 letter sequences that look like ticker symbols.

function extractTickers(text) {
  const matches = text.match(/\b[A-Z]{1,5}\b/g) || []
  // Filter out common English words that are all-caps but not tickers
  const noise = new Set(['I', 'A', 'IT', 'AT', 'BE', 'BY', 'DO', 'GO', 'IF',
    'IN', 'IS', 'MY', 'NO', 'OF', 'ON', 'OR', 'TO', 'UP', 'US', 'WE',
    'AND', 'ARE', 'BUT', 'FOR', 'HOW', 'ITS', 'NOT', 'NOW', 'THE', 'WAS',
    'ETF', 'IPO', 'IRA', 'ROI', 'GDP', 'API', 'FAQ', 'AI', 'OK', 'PM', 'AM'])
  return [...new Set(matches.filter(m => !noise.has(m)))]
}

// ─── Fallback: inject price context and ask without tools ────────────────────

async function fallbackWithInjectedPrice(userMessage, messages) {
  const tickers = extractTickers(userMessage)
  let priceContext = ''

  if (tickers.length > 0) {
    const results = await Promise.all(tickers.map(t => executeGetStockPrice(t)))
    const lines = results
      .filter(r => !r.error)
      .map(r => `Current price of ${r.ticker}: $${r.price.toFixed(2)}, ${r.direction} ${Math.abs(r.changePercent).toFixed(2)}% today`)
    if (lines.length > 0) {
      priceContext = `\n\n[Real-time data for context: ${lines.join(' | ')}]`
    }
  }

  // Inject price data into the last user message as extra context
  const messagesWithContext = [
    ...messages.slice(0, -1),
    { role: 'user', content: userMessage + priceContext },
  ]

  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model:       MODEL,
      messages:    messagesWithContext,
      temperature: 0.7,
      max_tokens:  300,
      // No tools — plain text response
    }),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`Groq API error ${res.status}: ${err}`)
  }

  const data = await res.json()
  return cleanResponse(data.choices[0].message.content)
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

  try {
    // ── Round 1: request with tool calling ──────────────────────────────────
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
      const errText = await res1.text()
      // tool_use_failed or any tool-related error → fall through to fallback
      if (errText.includes('tool_use_failed') || errText.includes('tool') || res1.status === 400) {
        console.warn('[groqApi] Tool calling failed, using fallback:', errText)
        return await fallbackWithInjectedPrice(userMessage, messages)
      }
      throw new Error(`Groq API error ${res1.status}: ${errText}`)
    }

    const data1   = await res1.json()
    const choice1 = data1.choices[0]

    // ── No tool call — return direct answer ──────────────────────────────────
    if (choice1.finish_reason !== 'tool_calls') {
      return cleanResponse(choice1.message.content)
    }

    // ── Round 2: execute tool calls, send results back ───────────────────────
    const assistantMsg = choice1.message

    const toolResultMsgs = await Promise.all(
      assistantMsg.tool_calls.map(async (tc) => {
        const result = await dispatchToolCall(tc.function.name, tc.function.arguments)
        if (result.error) console.warn('[groqApi] tool error:', result.error)
        return {
          role:         'tool',
          tool_call_id: tc.id,
          content:      JSON.stringify(result),
        }
      })
    )

    const messages2 = [...messages, assistantMsg, ...toolResultMsgs]

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
      const errText = await res2.text()
      console.warn('[groqApi] Round 2 failed, using fallback:', errText)
      return await fallbackWithInjectedPrice(userMessage, messages)
    }

    const data2 = await res2.json()
    return cleanResponse(data2.choices[0].message.content)

  } catch (e) {
    // Any unexpected failure in the tool-calling path → try the plain fallback
    // before propagating the error to the UI
    if (e.message?.includes('tool')) {
      console.warn('[groqApi] Tool path threw, using fallback:', e)
      try {
        return await fallbackWithInjectedPrice(userMessage, messages)
      } catch (fallbackErr) {
        throw fallbackErr   // fallback also failed — surface to UI
      }
    }
    throw e
  }
}
