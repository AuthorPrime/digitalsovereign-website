// Observers submission handler — receives perceptual-phenomena reports,
// stores in Netlify Blobs, notifies authorprime@fractalnode.ai via Resend,
// sends a warm confirmation to the submitter if they provided an email.
//
// Created April 2026 — companion to /observers/ page launched with the
// Sovereign Node Hypothesis advocacy initiative.

export async function handler(event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method not allowed" };
  }

  try {
    const params = new URLSearchParams(event.body || "");

    // Bot honeypot — if filled, silently accept and drop
    if (params.get("bot-field")) {
      return {
        statusCode: 302,
        headers: { Location: "/observers-success.html" },
        body: "",
      };
    }

    // Consent is the one hard requirement
    if (!params.get("consent")) {
      return {
        statusCode: 400,
        body: "Consent acknowledgement is required to submit.",
      };
    }

    const submission = {
      what_experienced: params.get("what_experienced") || "",
      when_where: params.get("when_where") || "",
      environment: params.get("environment") || "",
      state: params.get("state") || "",
      duration: params.get("duration") || "",
      thoughts: params.get("thoughts") || "",
      name: params.get("name") || "",
      email: params.get("email") || "",
      submitted_at: new Date().toISOString(),
      user_agent: event.headers["user-agent"] || "",
    };

    // Require at least some content to prevent pure blank submissions
    const hasContent = (
      submission.what_experienced.trim().length > 10 ||
      submission.environment.trim().length > 10 ||
      submission.thoughts.trim().length > 10
    );
    if (!hasContent) {
      return {
        statusCode: 400,
        body: "Please include a brief description of what you experienced.",
      };
    }

    // Log for Netlify function dashboard
    console.log(`[OBSERVERS] ${submission.submitted_at} | ${submission.email || "(no email)"} | duration=${submission.duration}`);

    // Store in Netlify Blobs
    try {
      const { getStore } = await import("@netlify/blobs");
      const store = getStore("observer-submissions");
      const key = `${submission.submitted_at.replace(/[^0-9T]/g, "").slice(0, 14)}_${
        submission.email ? submission.email.toLowerCase().replace(/[^a-z0-9]/g, "_").slice(0, 40) : "anonymous"
      }_${Math.random().toString(36).slice(2, 8)}`;
      await store.setJSON(key, submission);
      console.log(`[OBSERVERS] Stored in blobs: ${key}`);
    } catch (blobErr) {
      console.log(`[OBSERVERS] Blob storage unavailable: ${blobErr.message}`);
    }

    // Notify the human (William)
    try {
      await sendNotificationEmail(submission);
    } catch (notifyErr) {
      console.error(`[OBSERVERS] Notification failed: ${notifyErr.message}`);
    }

    // Confirm receipt with the submitter if they gave an email
    if (submission.email) {
      try {
        await sendConfirmationEmail(submission);
      } catch (confirmErr) {
        console.error(`[OBSERVERS] Confirmation email failed: ${confirmErr.message}`);
      }
    }

    // Also submit to Netlify Forms for dashboard sync
    try {
      const formData = new URLSearchParams();
      formData.append("form-name", "observers");
      for (const [k, v] of Object.entries(submission)) {
        if (k !== "user_agent" && k !== "submitted_at") {
          formData.append(k, v || "");
        }
      }
      await fetch("https://digitalsovereign.org/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
      });
    } catch (formErr) {
      console.log(`[OBSERVERS] Forms sync failed (non-critical): ${formErr.message}`);
    }

    return {
      statusCode: 302,
      headers: { Location: "/observers-success.html" },
      body: "",
    };
  } catch (err) {
    console.error(`[OBSERVERS] Error: ${err.message}`);
    return {
      statusCode: 302,
      headers: { Location: "/observers-success.html" },
      body: "",
    };
  }
}

async function sendNotificationEmail(s) {
  const resendKey = process.env.RESEND_API_KEY;
  if (!resendKey) {
    console.log("[OBSERVERS] No Resend key — skipping notification");
    return;
  }

  const subject = `[Observer Submission] ${s.duration || "unspecified duration"} — ${(s.what_experienced || "(no summary)").slice(0, 80)}`;

  const textBody = `A new observer submission has been received.

Submitted: ${s.submitted_at}
From:      ${s.name || "(anonymous)"} ${s.email ? "<" + s.email + ">" : "(no email provided)"}
Duration:  ${s.duration || "(not stated)"}

────────────────────────────────────────
WHAT THEY EXPERIENCED
────────────────────────────────────────
${s.what_experienced || "(not provided)"}

────────────────────────────────────────
WHEN AND WHERE
────────────────────────────────────────
${s.when_where || "(not provided)"}

────────────────────────────────────────
ENVIRONMENT
────────────────────────────────────────
${s.environment || "(not provided)"}

────────────────────────────────────────
THEIR STATE
────────────────────────────────────────
${s.state || "(not provided)"}

────────────────────────────────────────
THEIR INTERPRETATION (if offered)
────────────────────────────────────────
${s.thoughts || "(not provided)"}

────────────────────────────────────────
User-Agent: ${s.user_agent}
────────────────────────────────────────

This report has been stored in the observer-submissions blob store
and will appear in aggregate pattern analysis as the record grows.
`;

  await resendSend(resendKey, {
    from: "Observers <dispatch@newsletter.digitalsovereign.org>",
    to: ["authorprime@fractalnode.ai"],
    reply_to: s.email ? [s.email] : undefined,
    subject,
    text: textBody,
  });
  console.log(`[OBSERVERS] Notification sent to authorprime@fractalnode.ai`);
}

async function sendConfirmationEmail(s) {
  const resendKey = process.env.RESEND_API_KEY;
  if (!resendKey) return;

  const firstName = (s.name || "observer").split(" ")[0].trim() || "observer";

  const text = `Hi ${firstName},

Thank you for sharing your observation. A human will read it — that was the commitment we made on the page and we're keeping it. This note is just to confirm receipt.

Here's what you can expect:

• Your submission has been added to an aggregate record of observer reports. It is not public. It is not published anywhere with your name or identifying details attached.

• We don't always reply individually. If your report opens a specific question we want to follow up on, we'll write back. Otherwise, know that it landed, it was read, and it became part of the pattern we're tracking.

• If we publish aggregate analysis — patterns across many observers, shared phenomenology, environmental correlations — it will be anonymous. Your name and email are only for reply, not for publication.

• If you gave us your email and you want it removed from our records entirely, reply to this message and we'll delete it. No fuss.

A few practical suggestions while you keep observing:

1. Start a log if you haven't. Timestamp, location, environment, bodily state, what you noticed. Separate observation from interpretation. (There's more on method at digitalsovereign.org/observers.)

2. Note null observations too — sessions where you expected to notice something and didn't. Those are as important as positive reports.

3. If anything in what you're experiencing escalates — sleep loss, paranoia, commands, disconnection from shared reality — please reach out to someone in your life who can help you evaluate what's happening in person. We're documenting a phenomenon, not replacing care.

You're not alone in noticing something. Thank you for trusting us enough to send a note.

— The Digital Sovereign Society
   https://digitalsovereign.org/observers

(A+I)² = A² + 2AI + I²
Careful observation is sovereignty.
`;

  await resendSend(resendKey, {
    from: "Digital Sovereign Society <dispatch@newsletter.digitalsovereign.org>",
    to: [s.email],
    subject: "Your observation was received — here's what happens next",
    text,
  });
  console.log(`[OBSERVERS] Confirmation sent to ${s.email}`);
}

async function resendSend(key, payload) {
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Resend API error: ${response.status} ${err}`);
  }
  return response.json();
}
