const WELCOME_HTML = (email) => `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>You're on the list.</title>
</head>
<body style="margin:0;padding:0;background-color:#080D20;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:52px 36px 48px;">

    <p style="text-align:center;font-family:Georgia,'Times New Roman',serif;font-style:italic;font-size:28px;font-weight:400;color:#0057FF;margin:0 0 44px;letter-spacing:-0.01em;">
      horizon
    </p>

    <h1 style="font-family:Georgia,'Times New Roman',serif;font-size:38px;font-weight:700;color:#FFFFFF;margin:0 0 20px;line-height:1.15;">
      You're on the list.
    </h1>

    <p style="font-size:16px;color:#9CA3AF;line-height:1.75;margin:0 0 40px;">
      We're building the investing app that actually speaks your language. Real signals. Real analysis. Plain English.<br /><br />
      You'll be the first to know when we go live.
    </p>

    <a
      href="https://horizon-alpha-inky.vercel.app"
      style="display:inline-block;background-color:#0057FF;color:#FFFFFF;text-decoration:none;padding:16px 36px;border-radius:12px;font-size:16px;font-weight:600;letter-spacing:0.01em;margin-bottom:52px;"
    >
      See Your Portfolio
    </a>

    <div style="border-top:1px solid #1E293B;padding-top:24px;">
      <p style="font-size:13px;color:#4B5563;margin:0;line-height:1.65;">
        Built for the generation that was told to invest and never shown how.
      </p>
    </div>

  </div>
</body>
</html>
`

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const { email } = req.body ?? {}

  if (!email || typeof email !== 'string' || !email.includes('@')) {
    return res.status(400).json({ error: 'A valid email address is required.' })
  }

  const apiKey = process.env.RESEND_API_KEY
  if (!apiKey) {
    return res.status(500).json({ error: 'Server configuration error.' })
  }

  try {
    // Welcome email to the subscriber
    const welcomeRes = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'Horizon <onboarding@resend.dev>',
        to: email,
        subject: "You're on the Horizon list.",
        html: WELCOME_HTML(email),
      }),
    })

    if (!welcomeRes.ok) {
      const body = await welcomeRes.json().catch(() => ({}))
      console.error('Resend welcome error:', body)
      return res.status(502).json({ error: 'Could not send email. Please try again.' })
    }

    // Internal notification
    await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'Horizon <onboarding@resend.dev>',
        to: 'kianrajabtavousi@gmail.com',
        subject: `New Horizon signup: ${email}`,
        html: `<p style="font-family:sans-serif;font-size:15px;">New signup: <strong>${email}</strong></p>`,
      }),
    }).catch((err) => console.error('Notification email failed (non-fatal):', err))

    return res.status(200).json({ success: true })
  } catch (err) {
    console.error('subscribe handler error:', err)
    return res.status(500).json({ error: 'Something went wrong. Please try again.' })
  }
}
