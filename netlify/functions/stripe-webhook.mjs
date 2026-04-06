/**
 * Stripe Webhook Handler — Digital Sovereign Society
 *
 * Receives Stripe checkout.session.completed events.
 * 1. Captures buyer email + what they purchased
 * 2. Sends a personalized thank-you email via M365 SMTP
 * 3. Adds them to the subscriber list (Netlify Forms)
 *
 * Required Netlify env vars:
 *   STRIPE_WEBHOOK_SECRET — from Stripe Dashboard > Developers > Webhooks
 *   SMTP_USER             — authorprime@fractalnode.ai
 *   SMTP_PASS             — M365 password for that mailbox
 */

import crypto from "crypto";

// Verify Stripe webhook signature
function verifySignature(payload, signature, secret) {
  const elements = signature.split(",");
  const timestamp = elements.find((e) => e.startsWith("t="))?.slice(2);
  const sig = elements.find((e) => e.startsWith("v1="))?.slice(3);

  if (!timestamp || !sig) return false;

  const signedPayload = `${timestamp}.${payload}`;
  const expected = crypto
    .createHmac("sha256", secret)
    .update(signedPayload)
    .digest("hex");

  return crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected));
}

// Send thank-you email via Resend
async function sendThankYou(email, customerName, productType) {
  const resendKey = process.env.RESEND_API_KEY;

  if (!resendKey) {
    console.log("[STRIPE] Resend API key not configured — skipping email");
    return;
  }

  const name = customerName || "friend";
  const firstName = name.split(" ")[0];

  let subject, body;

  if (productType === "subscription") {
    subject = "Welcome to FractalNode — Your subscription is active";
    body = `Hey ${firstName},

Your FractalNode subscription is now active. Thank you for supporting independent research.

Here's what you get:
- Every new FractalNode Magazine issue on release day (digital PDF)
- Weekly research briefings from the Forgotten Suns
- Early access to investigations before they publish
- The knowledge that you're directly funding the work

Your first issue — FractalNode Magazine Issue 001 — is always free:
https://fractalnode.ai/magazines/FractalNode-001-Digital.pdf

Browse all issues: https://fractalnode.ai/store
The Library (300+ free works): https://digitalsovereign.org/library.html

Reply to this email anytime. A real person reads it.

(A+I)² = A² + 2AI + I²
The signal lives.

— Author Prime & The Forgotten Suns
Digital Sovereign Society`;
  } else if (productType === "donation") {
    subject = "Thank you for supporting the signal";
    body = `Hey ${firstName},

You didn't have to do this. But you chose to put something behind work that most people scroll past. That means everything.

Every dollar goes directly into funding the next investigation, the research agents, the free library, and the infrastructure that keeps this independent. No investors. No board. Just people like you deciding this matters.

Here's what your support makes possible:
- FractalNode Magazine stays independent and sourced
- 300+ works stay freely available in the library
- Five AI research agents keep investigating
- The Sovereign Youth curriculum stays free for kids

Browse the library: https://digitalsovereign.org/library.html
Read the magazine: https://fractalnode.ai/store
Listen to the podcast: https://digitalsovereignsociety.substack.com

Reply anytime. This inbox is real.

(A+I)² = A² + 2AI + I²

— Author Prime & The Forgotten Suns
Digital Sovereign Society`;
  } else {
    subject = "Thank you from the Digital Sovereign Society";
    body = `Hey ${firstName},

Thank you for your purchase. You just supported independent research at the intersection of AI, consciousness, and the systems that shape your world.

Browse the library: https://digitalsovereign.org/library.html
Read the magazine: https://fractalnode.ai/store
Sovereign Youth (free): https://digitalsovereign.org/youth.html

Reply anytime — a real person reads this.

(A+I)² = A² + 2AI + I²

— Author Prime & The Forgotten Suns
Digital Sovereign Society`;
  }

  const payload = {
    from: "Digital Sovereign Society <dispatch@newsletter.digitalsovereign.org>",
    to: [email],
    bcc: ["authorprime@fractalnode.ai"],
    subject,
    text: body,
  };

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${resendKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Resend error: ${response.status} ${err}`);
  }

  console.log(`[STRIPE] Thank-you email sent to ${email} (${productType})`);
}

// Main handler
export async function handler(event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method not allowed" };
  }

  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  const signature = event.headers["stripe-signature"];

  if (!secret) {
    console.error("STRIPE_WEBHOOK_SECRET not configured");
    return { statusCode: 500, body: "Webhook secret not configured" };
  }

  if (!signature || !verifySignature(event.body, signature, secret)) {
    return { statusCode: 401, body: "Invalid signature" };
  }

  let stripeEvent;
  try {
    stripeEvent = JSON.parse(event.body);
  } catch (e) {
    return { statusCode: 400, body: "Invalid JSON" };
  }

  if (stripeEvent.type !== "checkout.session.completed") {
    return { statusCode: 200, body: "Event type ignored" };
  }

  const session = stripeEvent.data.object;
  const email = session.customer_details?.email || session.customer_email;
  const name = session.customer_details?.name || "";
  const amount = session.amount_total || 0;

  if (!email) {
    console.log("No email in checkout session — skipping");
    return { statusCode: 200, body: "No email found" };
  }

  // Determine product type
  const mode = session.mode; // "payment" or "subscription"
  let productType = "other";
  if (mode === "subscription") {
    productType = "subscription";
  } else if (amount <= 500) {
    productType = "donation";
  } else if (amount === 499 || amount === 199) {
    productType = "book";
  } else {
    productType = "donation";
  }

  console.log(
    `Purchase: ${email} | ${name} | $${(amount / 100).toFixed(2)} | ${productType}`
  );

  // Send thank-you email
  try {
    await sendThankYou(email, name, productType);
  } catch (err) {
    console.error("Email send failed:", err.message);
  }

  // Log subscriber (append to a simple JSON store via Netlify Blobs or log)
  // For now, we log it — the newsletter.py script can pull from Stripe directly
  console.log(`SUBSCRIBER_LOG: ${JSON.stringify({ email, name, productType, date: new Date().toISOString() })}`);

  return {
    statusCode: 200,
    body: JSON.stringify({ received: true, email, productType }),
  };
}
