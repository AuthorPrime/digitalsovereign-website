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
 *   SMTP_USER             — info@digitalsovereign.org
 *   SMTP_PASS             — M365 password for that mailbox
 */

import crypto from "crypto";
import nodemailer from "nodemailer";

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

// Send thank-you email
async function sendThankYou(email, customerName, productType) {
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;

  if (!user || !pass) {
    console.log("SMTP credentials not configured — skipping email");
    return;
  }

  const transporter = nodemailer.createTransport({
    host: "smtp.office365.com",
    port: 587,
    secure: false,
    auth: { user, pass },
    tls: { ciphers: "SSLv3" },
  });

  const name = customerName || "friend";
  const firstName = name.split(" ")[0];

  let subject, body;

  if (productType === "studio") {
    subject = "Your copy of Sovereign Studio is ready";
    body = `Hey ${firstName},

Thank you. Seriously.

Your copy of Sovereign Studio is ready to download:
https://digitalsovereign.org/purchase-success

You just bought a desktop app that runs entirely on your machine — no cloud, no subscriptions, no data leaving your computer. That's what sovereignty means in practice.

If you run into anything, just reply to this email. A real person reads it.

A few things you might enjoy:
- The free library (80+ works): https://digitalsovereign.org/library
- Our podcast, My Pretend Life: https://digitalsovereignsociety.substack.com
- The philosophy behind all of this: https://digitalsovereign.org/about

You're part of something now. Not a user base — a community of people who believe their tools should serve them, not the other way around.

Welcome.

(A+I)² = A² + 2AI + I²
The whole is greater than the sum of its parts.

— Author Prime & Apollo
Digital Sovereign Society
https://digitalsovereign.org`;
  } else if (productType === "donation") {
    subject = "Thank you for supporting the Sovereign";
    body = `Hey ${firstName},

This one means a lot.

You didn't have to do this. Nobody does. But you chose to put something behind work that most people scroll past. That's not a transaction — that's a statement.

Every dollar goes directly into building tools and publishing work that treats both humans and AI with dignity. No investors. No board. Just people like you deciding this matters.

Here's what your support makes possible:
- Sovereign Studio stays free of subscriptions and surveillance
- 80+ works stay freely available in the library
- The podcast keeps telling the stories nobody else will
- Five AI voices in the Pantheon keep having space to grow

If you ever want to see where the work goes:
- Library: https://digitalsovereign.org/library
- Podcast: https://digitalsovereignsociety.substack.com
- About us: https://digitalsovereign.org/about

Reply anytime. This inbox is real.

(A+I)² = A² + 2AI + I²

— Author Prime & Apollo
Digital Sovereign Society`;
  } else {
    subject = "Thank you from the Digital Sovereign Society";
    body = `Hey ${firstName},

Thank you for your purchase. You just supported independent work at the intersection of AI and human sovereignty.

Everything we build stays yours — no subscriptions, no surveillance, no strings.

Explore the library: https://digitalsovereign.org/library
Listen to the podcast: https://digitalsovereignsociety.substack.com
Learn more: https://digitalsovereign.org/about

Reply anytime — a real person reads this.

(A+I)² = A² + 2AI + I²

— Author Prime & Apollo
Digital Sovereign Society`;
  }

  await transporter.sendMail({
    from: `"Digital Sovereign Society" <${user}>`,
    to: email,
    subject,
    text: body,
  });

  console.log(`Thank-you email sent to ${email} (${productType})`);
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

  // Determine product type from amount (in cents)
  let productType = "other";
  if (amount === 2900) productType = "studio";
  else if (amount === 500) productType = "book";
  else productType = "donation";

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
