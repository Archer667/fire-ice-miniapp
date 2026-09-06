import { createHmac } from 'node:crypto';

// Vercel supplies x-vercel-forwarded-for. Never trust caller-supplied x-login-*.
export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'GET') return res.status(405).end();
  const authorization = req.headers.authorization || '';
  const headers = { authorization };
  const ip = req.headers['x-vercel-forwarded-for'];
  const secret = process.env.LOGIN_AUDIT_SECRET;
  if (secret && typeof ip === 'string' && !ip.includes(',')) {
    const stamp = String(Math.floor(Date.now() / 1000));
    headers['x-login-ip'] = ip;
    headers['x-login-time'] = stamp;
    headers['x-login-signature'] = createHmac('sha256', secret)
      .update([stamp, ip, authorization].join('\n')).digest('hex');
  }
  try {
    const response = await fetch('https://valyria-game.duckdns.org/api/players/me', {
      headers, signal: AbortSignal.timeout(15000), redirect: 'error',
    });
    res.setHeader('Content-Type', 'application/json');
    return res.status(response.status).send(await response.text());
  } catch {
    return res.status(502).json({ detail: 'ارتباط با سرور برقرار نشد؛ دوباره تلاش کن.' });
  }
}
