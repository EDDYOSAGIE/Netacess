import Link from "next/link";
import { Header } from "@/components/Header";

function ScreenFrame({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="walk-frame" aria-label={`${label} screen preview`}>
      <div className="walk-browser"><span /><span /><span /><b>{label}</b></div>
      <div className="walk-screen">{children}</div>
    </div>
  );
}

export default function HowItWorks() {
  return (
    <>
      <Header />
      <main className="walk-page">
        <section className="walk-intro">
          <span className="walk-kicker">NETACCESS · CUSTOMER GUIDE</span>
          <h1>From plan to connected in a few steps.</h1>
          <p className="lead">Choose the plan that suits you, pay securely, and find your access code in your account. Here is what each step looks like.</p>
          <Link href="/#plans" className="btn">Browse plans</Link>
        </section>

        <section className="walk-step">
          <div className="walk-copy">
            <span className="walk-count">01 / CHOOSE</span>
            <h2>Pick your plan</h2>
            <p>Compare the available plans on the home page. Choose a one-time plan or a monthly renewal, then continue to checkout.</p>
            <Link href="/#plans" className="walk-text-link">See available plans <span aria-hidden="true">→</span></Link>
          </div>
          <ScreenFrame label="netaccessint.com · Plans">
            <div className="mock-brand"><span className="mock-mark">N</span><b>NetAccess</b><span>Plans</span></div>
            <div className="mock-title">Choose your plan</div>
            <div className="mock-plan-row"><span><b>One-time plan</b><small>30 days · Pay once</small></span><strong>₦10,000</strong></div>
            <div className="mock-plan-row selected"><span><b>Monthly plan</b><small>30 days · Renew when ready</small></span><strong>₦5,000</strong></div>
            <div className="mock-action">Choose monthly plan <span>→</span></div>
          </ScreenFrame>
        </section>

        <section className="walk-step reverse">
          <div className="walk-copy">
            <span className="walk-count">02 / ACCOUNT</span>
            <h2>Sign in or create an account</h2>
            <p>Continue with your NetAccess account. New here? Create an account with your details and verify your phone number. You will return to checkout afterward.</p>
            <Link href="/signup" className="walk-text-link">Create an account <span aria-hidden="true">→</span></Link>
          </div>
          <ScreenFrame label="NetAccess · Your account">
            <div className="mock-auth-brand"><span className="mock-mark">N</span><b>Welcome to NetAccess</b></div>
            <div className="mock-auth-card">
              <b>Create your account</b>
              <span className="mock-field-label">Full name</span><div className="mock-input">Your name</div>
              <span className="mock-field-label">Phone number</span><div className="mock-input">+234 800 000 0000</div>
              <div className="mock-action">Continue <span>→</span></div>
              <small>Already have an account? Log in</small>
            </div>
          </ScreenFrame>
        </section>

        <section className="walk-step">
          <div className="walk-copy">
            <span className="walk-count">03 / SECURE PAYMENT</span>
            <h2>Choose how to pay</h2>
            <p>Review your plan and total, then select an available payment method. Flutterwave supports card, bank transfer, USSD, and bank account payments. Espees will appear when available.</p>
          </div>
          <ScreenFrame label="NetAccess · Checkout">
            <div className="mock-checkout-heading"><span>Checkout</span><small>Step 1 of 1</small></div>
            <div className="mock-summary"><span>Your plan <b>Monthly plan</b></span><strong>₦5,000</strong></div>
            <div className="mock-payment selected"><i>✓</i><span><b>Flutterwave</b><small>Card, bank transfer, USSD or bank account</small></span></div>
            <div className="mock-payment"><i /> <span><b>Espees</b><small>Pay with your Espees wallet</small></span></div>
            <div className="mock-action">Pay ₦5,000 <span>→</span></div>
            <small className="mock-note">You will get your access code after payment is confirmed.</small>
          </ScreenFrame>
        </section>

        <section className="walk-step reverse">
          <div className="walk-copy">
            <span className="walk-count">04 / CONFIRMATION</span>
            <h2>Complete payment and get your code</h2>
            <p>Checkout opens the selected provider’s secure payment page. Once the payment is confirmed, your access code appears on the confirmation screen. You can copy it there.</p>
          </div>
          <ScreenFrame label="NetAccess · Payment confirmed">
            <div className="mock-success"><span>✓</span><b>Payment confirmed</b><small>You're all set. Your payment was received.</small></div>
            <div className="mock-code-box"><small>Your access code</small><strong>NA-••••-••••</strong><span>Copy code</span></div>
            <div className="mock-profile-button">Go to my profile <span>→</span></div>
            <small className="mock-note">Your real access code will appear here after confirmation.</small>
          </ScreenFrame>
        </section>

        <section className="walk-step">
          <div className="walk-copy">
            <span className="walk-count">05 / YOUR ACCOUNT</span>
            <h2>Come back to your profile any time</h2>
            <p>Your profile keeps your active plan, days remaining, access code, and transaction history together. Renew when you are ready; payments are not taken automatically.</p>
            <Link href="/profile" className="walk-text-link">Open my profile <span aria-hidden="true">→</span></Link>
          </div>
          <ScreenFrame label="NetAccess · My profile">
            <div className="mock-profile-top"><b>Hello, Ada</b><span>MY PROFILE</span></div>
            <div className="mock-profile-grid">
              <div className="mock-profile-card"><small>PLAN VALIDITY</small><strong>23 <em>days left</em></strong><div className="mock-progress"><i /></div><span>Monthly plan</span></div>
              <div className="mock-profile-card"><small>YOUR ACCESS CODE</small><strong className="mock-profile-code">NA-••••-••••</strong><span>Copy code</span></div>
            </div>
            <div className="mock-history"><b>Transaction history</b><span>Monthly plan <i>Successful</i></span></div>
          </ScreenFrame>
        </section>

        <section className="walk-contact" id="contact">
          <div className="walk-contact-heading">
            <span className="walk-count">WE’RE HERE TO HELP</span>
            <h2>Need a hand?</h2>
            <p>Contact NetAccess Systems Limited and our team will be glad to assist.</p>
          </div>
          <div className="walk-contact-items">
            <a href="tel:+234016317100" className="walk-contact-item"><span className="contact-symbol" aria-hidden="true">☎</span><span><small>CALL US</small><b>+234 01 631 7100</b></span></a>
            <a href="mailto:info@netaccessint.com" className="walk-contact-item"><span className="contact-symbol" aria-hidden="true">@</span><span><small>EMAIL</small><b>info@netaccessint.com</b></span></a>
            <div className="walk-contact-item"><span className="contact-symbol" aria-hidden="true">⌖</span><span><small>VISIT US</small><b>NetAccess Systems Limited</b><span>19 Ikorodu Road,<br />Maria Lodge (2nd Floor)<br />Maryland - Lagos, Nigeria.</span></span></div>
          </div>
        </section>
      </main>
      <footer className="footer">NetAccess Systems Nigeria · +234 01 631 7100 · <a href="mailto:info@netaccessint.com">info@netaccessint.com</a></footer>
    </>
  );
}