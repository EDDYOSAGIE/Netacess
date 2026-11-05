import { Header } from "@/components/Header";

export default function TermsPage() {
  return (
    <>
      <Header />
      <main className="legal-page">
        <div className="legal-draft" role="status">
          <strong>Draft for legal review</strong>
          <span>Do not treat this draft as final. Nigerian counsel must review it and the business details below must be completed before launch.</span>
        </div>
        <article className="legal-prose">
          <p className="hint">Version 2026-11-05-draft.1</p>
          <h1>Terms of Service</h1>
          <p>These draft terms describe use of the Netacess website and broadband plan checkout. They are not final until approved by the service operator and its Nigerian legal adviser.</p>
          <h2>Accounts</h2>
          <p>Provide accurate account details and keep your sign-in credentials and access codes private. Phone verification is used to confirm control of the number associated with an account. Tell Netacess promptly if you believe someone has accessed your account without permission.</p>
          <h2>Plans and payment</h2>
          <p>Review the plan, validity period, currency, total price and payment provider shown at checkout before placing an order. Payment is handled through the provider presented at checkout. An access code is issued after the payment is confirmed.</p>
          <h2>Service and access codes</h2>
          <p>Use access codes only for the plan and service for which they were issued. Network availability and performance can depend on factors outside the website operator’s control; the operator must state the applicable service commitments in the final terms.</p>
          <h2>Cancellations, refunds and complaints</h2>
          <p><strong>Business decision required:</strong> publish the actual cancellation, renewal, refund, complaint and support processes here, consistent with the checkout flow and applicable consumer-protection requirements.</p>
          <h2>Operator and governing terms</h2>
          <p><strong>Business details required:</strong> insert the contracting entity’s registered name, address, support contact, governing-law and dispute-resolution terms, and effective date after legal review.</p>
        </article>
      </main>
    </>
  );
}