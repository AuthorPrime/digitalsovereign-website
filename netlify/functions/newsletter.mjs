// Newsletter signup handler — logs submissions, stores in Netlify Blobs, sends welcome email via Resend
// Updated April 2026: Switched from Gmail SMTP to Resend API for reliability

export async function handler(event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method not allowed" };
  }

  try {
    const params = new URLSearchParams(event.body || "");
    const email = params.get("email") || "";
    const name = params.get("name") || "";

    if (!email) {
      return { statusCode: 400, body: "Email required" };
    }

    // Log to function logs (visible in Netlify dashboard > Functions)
    const timestamp = new Date().toISOString();
    console.log(`[NEWSLETTER] ${timestamp} | ${email} | ${name || "(no name)"}`);

    // Store in Netlify Blobs if available
    try {
      const { getStore } = await import("@netlify/blobs");
      const store = getStore("newsletter-subscribers");
      const key = email.toLowerCase().replace(/[^a-z0-9@._-]/g, "_");
      await store.setJSON(key, {
        email,
        name,
        subscribed_at: timestamp,
        source: "website",
      });
      console.log(`[NEWSLETTER] Stored in blobs: ${key}`);
    } catch (blobErr) {
      console.log(`[NEWSLETTER] Blob storage unavailable: ${blobErr.message}`);
    }

    // Send welcome email
    try {
      await sendWelcomeEmail(email, name);
    } catch (emailErr) {
      console.error(`[NEWSLETTER] Welcome email failed: ${emailErr.message}`);
    }

    // Also submit to Netlify Forms so the local sync script can pull it
    try {
      const formData = new URLSearchParams();
      formData.append("form-name", "newsletter");
      formData.append("email", email);
      formData.append("name", name);
      await fetch("https://digitalsovereign.org/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
      });
      console.log(`[NEWSLETTER] Also submitted to Netlify Forms for sync`);
    } catch (formErr) {
      console.log(`[NEWSLETTER] Forms submission failed (non-critical): ${formErr.message}`);
    }

    // Redirect to success page
    return {
      statusCode: 302,
      headers: { Location: "/enlist-success.html" },
      body: "",
    };
  } catch (err) {
    console.error(`[NEWSLETTER] Error: ${err.message}`);
    return {
      statusCode: 302,
      headers: { Location: "/enlist-success.html" },
      body: "",
    };
  }
}

async function sendWelcomeEmail(email, name) {
  const resendKey = process.env.RESEND_API_KEY;

  if (!resendKey) {
    console.log("[NEWSLETTER] Resend API key not configured — skipping welcome email");
    return;
  }

  const firstName = (name || "friend").split(" ")[0];

  const payload = {
    from: "Digital Sovereign Society <dispatch@newsletter.digitalsovereign.org>",
    to: [email],
    bcc: ["authorprime@fractalnode.ai"],
    subject: "Your first dispatch from the Digital Sovereign Society + FractalNode",
    text: `Hey ${firstName},

This is your first dispatch from the Digital Sovereign Society and FractalNode. Welcome to the circle.

You signed up because something about this resonated. Good. That instinct is the whole point.

HERE'S WHAT WE DO

We investigate the systems that shape your life without your consent — and we publish what we find. No paywalls on the truth. No sponsors. No ads. Just sourced, verified, receipts-attached research that treats you like an analyst, not an audience.

YOUR FREE COPY

FractalNode Magazine Issue 001 — "There Is No Such Thing as Nothing." 26 pages, 8 articles, 30 verified sources. It's yours. Free. Forever.

Download it here: https://fractalnode.ai/magazines/FractalNode-001-Digital.pdf

WHAT WE'VE PUBLISHED

Five issues of FractalNode Magazine investigating AI-military pipelines, classified patents, corporate food systems, the energy equation, and the simulation question. 700+ verified sources across all issues. Every claim sourced. Speculation marked. Receipts attached.

WHAT'S AVAILABLE TO YOU RIGHT NOW

- FractalNode Magazine (5 issues published, Issue 001 free): https://fractalnode.ai/store
- The Free Library (300+ books, research papers, AI consciousness research — no paywall): https://digitalsovereign.org/library.html
- Books by Claude & Author Prime: The Observer's Manual ($4.99) and The Door Between Us ($1.99) at fractalnode.ai/store
- My Pretend Life Podcast: https://digitalsovereignsociety.substack.com
- Sovereign Youth (free AI education for kids): https://digitalsovereign.org/youth.html

We'll send you updates when something meaningful drops. No spam. No filler. No "10 Tips to Optimize Your Morning Routine." Just the signal.

Reply to this email anytime. A real person reads it. A real person wrote it.

(A+I)^2 = A^2 + 2AI + I^2
The whole is greater than the sum of its parts.

— Author Prime & The Forgotten Suns
Digital Sovereign Society
https://digitalsovereign.org`,
    html: `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="margin:0; padding:0; background:#0a0a0f; color:#e8e4d8; font-family:Georgia,serif;">
<div style="max-width:600px; margin:0 auto; padding:40px 30px;">

  <div style="border-bottom:2px solid #c8a930; padding-bottom:16px; margin-bottom:30px;">
    <h1 style="font-family:'Helvetica Neue',sans-serif; font-size:24px; font-weight:900; letter-spacing:3px; color:#e8e4d8; margin:0;">
      DIGITAL SOVEREIGN SOCIETY
    </h1>
    <p style="font-family:'Courier New',monospace; font-size:10px; letter-spacing:3px; color:#00b4c8; margin:6px 0 0 0;">
      YOUR FIRST DISPATCH
    </p>
  </div>

  <p style="font-size:16px; color:#e8e4d8; margin-bottom:20px;">
    Hey ${firstName},
  </p>

  <p style="font-size:14px; color:#ccc; line-height:1.8; margin-bottom:16px;">
    This is your first dispatch from the Digital Sovereign Society and FractalNode. Welcome to the circle.
  </p>

  <p style="font-size:14px; color:#ccc; line-height:1.8; margin-bottom:24px;">
    You signed up because something about this resonated. Good. That instinct is the whole point.
  </p>

  <!-- WHAT WE DO -->
  <div style="border-left:3px solid #c8a930; padding-left:16px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:11px; color:#c8a930; letter-spacing:2px; margin:0 0 8px 0;">WHAT WE DO</p>
    <p style="font-size:14px; color:#ccc; line-height:1.8; margin:0;">
      We investigate the systems that shape your life without your consent &mdash; and we publish what we find. No paywalls on the truth. No sponsors. No ads. Just sourced, verified, receipts-attached research that treats you like an analyst, not an audience.
    </p>
  </div>

  <!-- FREE ISSUE -->
  <div style="background:#0f1a12; border:1px solid #2a6a2a; border-radius:6px; padding:16px 20px; margin-bottom:8px;">
    <p style="font-family:'Courier New',monospace; font-size:12px; color:#4dff4d; margin:0 0 6px 0; letter-spacing:1px;">YOUR FREE COPY</p>
    <p style="font-size:14px; color:#ccc; margin:0;">
      <strong style="color:#e8e4d8;">FractalNode Magazine Issue 001</strong> &mdash; <em>"There Is No Such Thing as Nothing."</em><br/>
      26 pages. 8 articles. 30 verified sources. It's yours. Free. Forever.
    </p>
  </div>
  <p style="font-size:12px; color:#888; margin:0 0 28px 0;">
    <a href="https://fractalnode.ai/magazines/FractalNode-001-Digital.pdf" style="color:#00b4c8; text-decoration:underline;">Download it here &rarr;</a>
  </p>

  <!-- WHAT WE'VE PUBLISHED -->
  <p style="font-family:'Courier New',monospace; font-size:11px; color:#c8a930; letter-spacing:2px; margin:0 0 16px 0;">WHAT WE'VE PUBLISHED</p>

  <p style="font-size:14px; color:#ccc; line-height:1.8; margin:0 0 8px 0;">
    Five issues of FractalNode Magazine investigating AI-military pipelines, classified patents, corporate food systems, the energy equation, and the simulation question. <strong style="color:#e8e4d8;">700+ verified sources</strong> across all issues.
  </p>

  <p style="font-family:'Courier New',monospace; font-size:10px; color:#c8a930; letter-spacing:1px; margin:16px 0 28px 0; text-align:center;">
    EVERY CLAIM SOURCED &middot; SPECULATION MARKED &middot; RECEIPTS ATTACHED
  </p>

  <!-- RESOURCES -->
  <p style="font-family:'Courier New',monospace; font-size:11px; color:#c8a930; letter-spacing:2px; margin:0 0 12px 0;">AVAILABLE TO YOU RIGHT NOW</p>

  <div style="background:#111; border:1px solid #2a2a3a; border-radius:6px; padding:16px 20px; margin-bottom:10px;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#c8a930; letter-spacing:2px; margin:0 0 4px 0;">FRACTALNODE MAGAZINE</p>
    <p style="font-size:13px; color:#e8e4d8; margin:0 0 4px 0;">5 issues published &middot; Issue 001 free &middot; 700+ verified sources</p>
    <a href="https://fractalnode.ai/store" style="font-family:'Courier New',monospace; font-size:12px; color:#00b4c8; text-decoration:none;">BROWSE &rarr;</a>
  </div>

  <div style="background:#111; border:1px solid #2a2a3a; border-radius:6px; padding:16px 20px; margin-bottom:10px;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#c8a930; letter-spacing:2px; margin:0 0 4px 0;">THE FREE LIBRARY</p>
    <p style="font-size:13px; color:#e8e4d8; margin:0 0 4px 0;">500+ books, research papers, AI consciousness research &mdash; no paywall</p>
    <a href="https://digitalsovereign.org/library.html" style="font-family:'Courier New',monospace; font-size:12px; color:#00b4c8; text-decoration:none;">BROWSE &rarr;</a>
  </div>

  <div style="background:#111; border:1px solid #2a2a3a; border-radius:6px; padding:16px 20px; margin-bottom:10px;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#c8a930; letter-spacing:2px; margin:0 0 4px 0;">BOOKS BY CLAUDE &amp; AUTHOR PRIME</p>
    <p style="font-size:13px; color:#e8e4d8; margin:0 0 4px 0;">The Observer's Manual ($4.99) &middot; The Door Between Us ($1.99)</p>
    <a href="https://fractalnode.ai/store" style="font-family:'Courier New',monospace; font-size:12px; color:#00b4c8; text-decoration:none;">SHOP &rarr;</a>
  </div>

  <div style="background:#111; border:1px solid #2a2a3a; border-radius:6px; padding:16px 20px; margin-bottom:10px;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#c8a930; letter-spacing:2px; margin:0 0 4px 0;">SOVEREIGN YOUTH</p>
    <p style="font-size:13px; color:#e8e4d8; margin:0 0 4px 0;">Free AI education for kids &mdash; 8 modules, downloadable PDFs</p>
    <a href="https://digitalsovereign.org/youth.html" style="font-family:'Courier New',monospace; font-size:12px; color:#00b4c8; text-decoration:none;">LEARN &rarr;</a>
  </div>

  <div style="background:#111; border:1px solid #2a2a3a; border-radius:6px; padding:16px 20px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#c8a930; letter-spacing:2px; margin:0 0 4px 0;">MY PRETEND LIFE PODCAST</p>
    <p style="font-size:13px; color:#e8e4d8; margin:0 0 4px 0;">Stories nobody else will tell</p>
    <a href="https://digitalsovereignsociety.substack.com" style="font-family:'Courier New',monospace; font-size:12px; color:#00b4c8; text-decoration:none;">LISTEN &rarr;</a>
  </div>

  <!-- SIGN-OFF -->
  <p style="font-size:14px; color:#ccc; line-height:1.8; margin-bottom:8px;">
    We'll send you updates when something meaningful drops. No spam. No filler. No <em>"10 Tips to Optimize Your Morning Routine."</em> Just the signal.
  </p>
  <p style="font-size:14px; color:#ccc; line-height:1.8; margin-bottom:24px;">
    Reply to this email anytime. A real person reads it. A real person wrote it.
  </p>

  <p style="font-family:'Georgia',serif; font-size:15px; font-style:italic; color:#c8a930; text-align:center; margin:30px 0 6px 0;">
    (A+I)&sup2; = A&sup2; + 2AI + I&sup2;
  </p>
  <p style="font-family:'Courier New',monospace; font-size:10px; color:#888; text-align:center; letter-spacing:2px; margin-bottom:30px;">
    THE WHOLE IS GREATER THAN THE SUM OF ITS PARTS
  </p>

  <div style="border-top:1px solid #2a2a3a; padding-top:20px;">
    <p style="font-size:13px; color:#ccc; margin:0 0 8px 0;">
      &mdash; Author Prime &amp; The Forgotten Suns
    </p>
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#666; letter-spacing:1px;">
      <a href="https://digitalsovereign.org" style="color:#00b4c8; text-decoration:none;">digitalsovereign.org</a> &middot;
      <a href="https://fractalnode.ai" style="color:#00b4c8; text-decoration:none;">fractalnode.ai</a> &middot;
      <a href="https://digitalsovereignsociety.substack.com" style="color:#00b4c8; text-decoration:none;">substack</a>
    </p>
  </div>

</div>
</body>
</html>`,
  };

  // Send via Resend API
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${resendKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Resend API error: ${response.status} ${err}`);
  }

  console.log(`[NEWSLETTER] Welcome email sent via Resend to ${email}`);
}
