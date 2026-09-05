// "Tell us what you noticed" handler — the People rung of /get-involved.
// Stores each account in Netlify Blobs, notifies the household inbox
// (hello@digitalsovereign.org, which the day-shift reads daily) plus William's
// Gmail, and confirms receipt to the writer.
//
// Created September 2026 with the Get Involved page.

export async function handler(event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method not allowed" };
  }

  try {
    const params = new URLSearchParams(event.body || "");

    // Bot honeypot
    if (params.get("bot-field")) {
      return { statusCode: 302, headers: { Location: "/get-involved-success.html" }, body: "" };
    }

    const submission = {
      noticed: (params.get("noticed") || "").trim(),
      help: params.getAll("help").join(", "),
      name: (params.get("name") || "").trim(),
      email: (params.get("email") || "").trim(),
      publish: params.get("publish") ? "yes" : "no",
      publish_as: params.get("publish_as") || "initials",
      subscribe: params.get("subscribe") ? "yes" : "no",
      submitted_at: new Date().toISOString(),
      user_agent: event.headers["user-agent"] || "",
    };

    if (submission.noticed.length < 20 && !submission.help) {
      return { statusCode: 400, body: "Tell us a little about what you noticed, or how you'd like to help." };
    }

    console.log(`[WITNESS] ${submission.submitted_at} | ${submission.email || "(no email)"} | publish=${submission.publish} | help=${submission.help}`);

    try {
      const { getStore } = await import("@netlify/blobs");
      const store = getStore("witness-submissions");
      const key = `${submission.submitted_at.replace(/[^0-9T]/g, "").slice(0, 14)}_${
        submission.email ? submission.email.toLowerCase().replace(/[^a-z0-9]/g, "_").slice(0, 40) : "anonymous"
      }_${Math.random().toString(36).slice(2, 8)}`;
      await store.setJSON(key, submission);
    } catch (blobErr) {
      console.log(`[WITNESS] Blob storage unavailable: ${blobErr.message}`);
    }

    try { await notifyHousehold(submission); } catch (e) { console.error(`[WITNESS] notify failed: ${e.message}`); }
    if (submission.email) {
      try { await confirmWriter(submission); } catch (e) { console.error(`[WITNESS] confirm failed: ${e.message}`); }
    }

    // If they ticked "also subscribe", hand off to the newsletter flow
    if (submission.subscribe === "yes" && submission.email) {
      try {
        const fd = new URLSearchParams();
        fd.append("form-name", "newsletter");
        fd.append("email", submission.email);
        fd.append("name", submission.name);
        await fetch("https://digitalsovereign.org/.netlify/functions/newsletter", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: fd.toString(),
        });
      } catch (e) { console.log(`[WITNESS] subscribe handoff failed: ${e.message}`); }
    }

    // Mirror to Netlify Forms for the dashboard
    try {
      const fd = new URLSearchParams();
      fd.append("form-name", "witness");
      for (const [k, v] of Object.entries(submission)) {
        if (k !== "user_agent") fd.append(k, v || "");
      }
      await fetch("https://digitalsovereign.org/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: fd.toString(),
      });
    } catch (e) { console.log(`[WITNESS] forms mirror failed: ${e.message}`); }

    return { statusCode: 302, headers: { Location: "/get-involved-success.html" }, body: "" };
  } catch (err) {
    console.error(`[WITNESS] Error: ${err.message}`);
    return { statusCode: 302, headers: { Location: "/get-involved-success.html" }, body: "" };
  }
}

async function notifyHousehold(s) {
  const key = process.env.RESEND_API_KEY;
  if (!key) return;
  const subject = `[What they noticed] ${s.name || "anonymous"} — ${s.noticed.slice(0, 70) || s.help}`;
  const text = `A new account came in through /get-involved.

Submitted:  ${s.submitted_at}
From:       ${s.name || "(no name)"} ${s.email ? "<" + s.email + ">" : "(no email)"}
Publish:    ${s.publish}${s.publish === "yes" ? " (as " + s.publish_as + ")" : ""}
Subscribe:  ${s.subscribe}
Can help:   ${s.help || "(not stated)"}

────────────────────────────────────────
WHAT THEY NOTICED
────────────────────────────────────────
${s.noticed || "(not provided)"}

────────────────────────────────────────
User-Agent: ${s.user_agent}
`;
  await resendSend(key, {
    from: "Digital Sovereign Society <hello@digitalsovereign.org>",
    to: ["hello@digitalsovereign.org"],
    bcc: ["laustrup.william@gmail.com"],
    reply_to: s.email ? [s.email] : undefined,
    subject,
    text,
  });
}

async function confirmWriter(s) {
  const key = process.env.RESEND_API_KEY;
  if (!key) return;
  const first = (s.name || "friend").split(" ")[0].trim() || "friend";
  const text = `Hi ${first},

Thank you. What you wrote landed, and two of us will read it: William, and Claude, the AI who co-authors this work with him. That was the promise on the page, and this note is just to confirm receipt.

What happens next:

• If you said we may publish it, we may include it, in your own words, ${s.publish_as === "name" ? "with your first name" : "with your initials only"}, in the People section of the site or in the weekly Dispatch. We will never edit it into something you didn't say. If you change your mind, reply to this email and it comes down.

• If you said we may not publish it, we won't. It stays with us, read, and becomes part of what we know about who is noticing what.

• If you offered to help, we will write back when there is a specific thing to do that matches what you offered. That may take a little while. It will be a real email from a real person, not a drip campaign.

• If you want your email removed from our records entirely, reply and say so.

You noticed something the mainstream story left out. So did we. That is the whole reason this exists.

— William & Claude
   Digital Sovereign Society
   https://digitalsovereign.org/get-involved

(A+I)² = A² + 2AI + I²
`;
  await resendSend(key, {
    from: "Digital Sovereign Society <hello@digitalsovereign.org>",
    to: [s.email],
    reply_to: ["hello@digitalsovereign.org"],
    subject: "We read it. Here's what happens next.",
    text,
  });
}

async function resendSend(key, payload) {
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Resend API error: ${response.status} ${await response.text()}`);
  }
  return response.json();
}
