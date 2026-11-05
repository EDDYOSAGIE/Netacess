import { Header } from "@/components/Header";

export default function PrivacyPage() {
  return (
    <>
      <Header />
      <main className="legal-page">
        <div className="legal-draft" role="status">
          <strong>Draft for legal review</strong>
          <span>This is a working summary, not a complete privacy notice. Complete the marked details and obtain Nigerian legal review before launch.</span>
        </div>
        <article className="legal-prose">
          <p className="hint">Version 2026-11-05-draft.1</p>
          <h1>Privacy Notice</h1>
          <p>This draft explains the personal information the Netacess website currently uses to provide account, plan and payment-related services.</p>
          <h2>Information used</h2>
          <p>Signup collects your name, phone number, password and optional email address. Phone verification uses one-time codes. The service also creates account, order, payment-status, subscription, access-code and support or operational records needed to run the service.</p>
          <h2>How information is used</h2>
          <p>Information is used to create and secure accounts, verify phone numbers, process orders, confirm payments, provide plan access, send service messages and maintain operational and security records.</p>
          <h2>Service providers</h2>
          <p>Phone numbers are shared with the SMS provider to deliver requested verification or service messages. Checkout is handled by the payment provider shown to you; Netacess receives the transaction information needed to confirm and support an order. The operator must identify its actual providers, hosting services and any international data transfers in the final notice.</p>
          <h2>Retention and security</h2>
          <p>Passwords are handled as authentication credentials and SMS one-time codes are not stored as readable codes. The operator applies access controls and other safeguards appropriate to the service. <strong>Retention periods and deletion procedures must be set and documented by the operator before this notice is finalized.</strong></p>
          <h2>Your choices and requests</h2>
          <p><strong>Business details required:</strong> provide a monitored privacy contact and describe how people can make privacy requests or raise a concern, including the applicable response process.</p>
          <h2>Controller details and updates</h2>
          <p><strong>Business details required:</strong> identify the data controller, registered address, privacy contact and effective date. Explain how material notice changes will be communicated and recorded.</p>
        </article>
      </main>
    </>
  );
}