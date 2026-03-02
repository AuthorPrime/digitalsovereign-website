// Newsletter signup handler — logs submissions and stores in Netlify Blobs

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
      // Blobs may not be available — that's OK, we still have the console log
      console.log(`[NEWSLETTER] Blob storage unavailable: ${blobErr.message}`);
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
