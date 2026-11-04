import type { APIRoute } from 'astro';
import { siteConfig } from '../../config/site';

export const prerender = false;

// In-memory sliding window rate limiter per IP: max 5 requests per 15 minutes
const RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000;
const MAX_REQUESTS_PER_WINDOW = 5;
const ipRequestHistory = new Map<string, number[]>();

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const timestamps = ipRequestHistory.get(ip) || [];
  const recent = timestamps.filter((ts) => now - ts < RATE_LIMIT_WINDOW_MS);
  recent.push(now);
  ipRequestHistory.set(ip, recent);
  return recent.length <= MAX_REQUESTS_PER_WINDOW;
}

export const POST: APIRoute = async ({ request }) => {
  const isProduction = import.meta.env.PROD || process.env.NODE_ENV === 'production';

  // 1. Client IP Extraction
  const forwardedFor = request.headers.get('x-forwarded-for');
  const clientIp = forwardedFor
    ? forwardedFor.split(',')[0].trim()
    : request.headers.get('x-real-ip') || '127.0.0.1';

  // 2. Per-IP Rate Limiting
  if (!checkRateLimit(clientIp)) {
    return new Response(
      JSON.stringify({
        success: false,
        message: 'Too many inquiries submitted from your IP address. Please wait a few minutes or call us directly.',
      }),
      { status: 429, headers: { 'Content-Type': 'application/json' } }
    );
  }

  try {
    const body = await request.json();
    const {
      name,
      email,
      phone,
      organization,
      facility_type,
      message,
      consent,
      b_website_hp,
      form_ts,
      'cf-turnstile-response': turnstileToken,
    } = body;

    // 3. Honeypot check (bot deception)
    if (b_website_hp) {
      // Fake success for bots
      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // 4. Submission duration check: must take at least 1.5 seconds
    if (form_ts) {
      const duration = Date.now() - Number(form_ts);
      if (duration < 1500) {
        return new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    // 5. Cloudflare Turnstile Verification (if secret configured)
    const turnstileSecret = process.env.TURNSTILE_SECRET_KEY || import.meta.env.TURNSTILE_SECRET_KEY;
    if (turnstileSecret) {
      if (!turnstileToken) {
        return new Response(
          JSON.stringify({ success: false, message: 'Cloudflare bot verification check failed.' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        );
      }

      const verifyRes = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          secret: turnstileSecret,
          response: turnstileToken,
          remoteip: clientIp,
        }),
      });

      const verifyData = await verifyRes.json();
      if (!verifyData.success) {
        return new Response(
          JSON.stringify({ success: false, message: 'Cloudflare verification failed. Please try again.' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        );
      }
    }

    // 6. Strict validation & length limits
    if (!name || typeof name !== 'string' || name.trim().length === 0 || name.length > 100) {
      return new Response(
        JSON.stringify({ success: false, message: 'Invalid name (1-100 characters).' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || typeof email !== 'string' || !emailRegex.test(email.trim()) || email.length > 100) {
      return new Response(
        JSON.stringify({ success: false, message: 'Please provide a valid email address (max 100 chars).' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (!phone || typeof phone !== 'string' || phone.trim().length < 6 || phone.length > 20) {
      return new Response(
        JSON.stringify({ success: false, message: 'Please provide a valid phone number (6-20 characters).' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (!organization || typeof organization !== 'string' || organization.length > 100) {
      return new Response(
        JSON.stringify({ success: false, message: 'Organization / Society name required (max 100 chars).' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (!message || typeof message !== 'string' || message.trim().length === 0 || message.length > 2000) {
      return new Response(
        JSON.stringify({ success: false, message: 'Message required (1-2000 characters).' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (!consent) {
      return new Response(
        JSON.stringify({ success: false, message: 'Consent is required to submit your inquiry.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // 7. Dispatch Email
    const resendApiKey = process.env.RESEND_API_KEY || import.meta.env.RESEND_API_KEY;
    const recipientEmail =
      process.env.CONTACT_RECIPIENT_EMAIL ||
      import.meta.env.CONTACT_RECIPIENT_EMAIL ||
      siteConfig.email;

    if (resendApiKey) {
      const emailPayload = {
        from: `Altsan Inquiries <noreply@altsan.com>`,
        to: [recipientEmail],
        reply_to: email.trim(),
        subject: `New Facility Inquiry: ${organization.trim()} (${facility_type || 'General'})`,
        text: `New Staffing Inquiry Received on altsan.com:
--------------------------------------------------
Full Name: ${name.trim()}
Email: ${email.trim()}
Phone: ${phone.trim()}
Organization / Society: ${organization.trim()}
Facility Type: ${facility_type || 'Not specified'}
IP Address: ${clientIp}

Requirement & Message:
${message.trim()}
--------------------------------------------------
Consent was explicitly checked by the user.
No data stored in marketing database.`,
      };

      const resendRes = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${resendApiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(emailPayload),
      });

      if (!resendRes.ok) {
        const resendErr = await resendRes.text();
        console.error('Email dispatch error from provider:', resendErr);
        return new Response(
          JSON.stringify({
            success: false,
            message: 'Email service error. Please contact us directly via phone or email.',
          }),
          { status: 502, headers: { 'Content-Type': 'application/json' } }
        );
      }
    } else {
      // If in production and no mail key configured, raise visible error
      if (isProduction) {
        return new Response(
          JSON.stringify({
            success: false,
            message: 'Inquiry delivery service is temporarily offline.',
          }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
      }

      // Local / Test simulation
      console.log('--- [MOCK DISPATCH] Contact Form Submission ---');
      console.log(`From: ${name} <${email}> | Phone: ${phone} | Org: ${organization}`);
      console.log(`Message: ${message}`);
      console.log('------------------------------------------------');
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Your inquiry has been received. Our operations team will contact you shortly.',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    console.error('Contact form submission processing failure:', error);
    return new Response(
      JSON.stringify({
        success: false,
        message: 'Internal server error processing inquiry. Please reach out to us directly.',
      }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
};

