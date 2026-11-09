import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What LibraryHive collects, who sees it, and which outside services your browser talks to.",
};

/**
 * DRAFT for review, not an approved legal document (SECURITY.md 17.2 and 19, item L2). Everything stated here was
 * checked against the code on 2026-10-22. Anything the team has not decided is a visible `Todo` placeholder; none of
 * them may be removed or invented without the project owner's approval.
 */
function Todo({ children }: { children: ReactNode }) {
  return (
    <mark className="rounded bg-amber-200 px-1 text-amber-900" data-placeholder="true">
      [To be confirmed before launch: {children}]
    </mark>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="text-xl font-bold text-slate-900">
        {title}
      </h2>
      {children}
    </section>
  );
}

function List({ children }: { children: ReactNode }) {
  return <ul className="ml-5 flex list-disc flex-col gap-1.5">{children}</ul>;
}

export default function PrivacyPage() {
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10 text-base leading-relaxed text-slate-700 sm:px-6">
      <header className="flex flex-col gap-3">
        <h1 className="font-display text-3xl font-bold text-slate-900">Privacy Policy</h1>
        <p role="note" className="rounded-lg border border-amber-300/40 bg-amber-100 px-4 py-3 text-sm text-amber-900">
          <strong>Draft for review.</strong> This page describes how LibraryHive works today. It has not been approved as a legal
          document, and the highlighted items still need a decision from the team. Last updated: <Todo>date, set on approval</Todo>
        </p>
        <p>
          LibraryHive helps students in India find study libraries, see which seats are free, book a seat and pay for it. It also
          helps library owners manage their seats, members, dues and payments. This page explains what information we handle, who can
          see it, and which outside services your browser contacts when you use the site.
        </p>
        <p>
          <strong>Who is responsible:</strong> <Todo>legal name and address of the business running LibraryHive</Todo>
        </p>
      </header>

      <Section id="you-give" title="Information you give us">
        <List>
          <li>
            <strong>Account:</strong> your name, phone number, a password (we keep only a scrambled form of it, never the password
            itself) and your role (student or library owner). An email address is used for sign-in and messages. Students can also
            choose the exam they are preparing for.
          </li>
          <li>
            <strong>Library owners:</strong> the library&apos;s name, description, address, area and city, contact phone and email,
            opening hours, photos, facilities, pricing plans, seat layout and the library&apos;s map location (see
            &quot;Location&quot; below). This is shown publicly on the library&apos;s page.
          </li>
          <li>
            <strong>Visit requests and complaints:</strong> the date, time slot and note you give when asking to visit a library, and
            the category and description of a complaint, together with the owner&apos;s replies.
          </li>
        </List>
      </Section>

      <Section id="from-use" title="Information created when you use LibraryHive">
        <List>
          <li>
            <strong>Bookings and memberships:</strong> the seat you hold or book, your pricing plan, start and due dates, and the
            status of your membership. When an owner archives a membership, they record a reason.
          </li>
          <li>
            <strong>Attendance:</strong> check-in and check-out times and how they were recorded (by you or by the owner).
          </li>
          <li>
            <strong>Payments:</strong> the amount, plan, method (online or cash recorded by the owner), status, receipt number, time,
            and the payment identifiers that Razorpay gives us. We do not receive or store your card, UPI or bank details.
          </li>
          <li>
            <strong>Notifications:</strong> messages inside the app about bookings, payments, dues and complaints. Some are also
            sent by email. Email delivery is handled by <Todo>email provider, not yet chosen</Todo>
          </li>
          <li>
            <strong>Security records:</strong> LibraryHive keeps an audit record of important actions (for example payments,
            admissions and changes by owners). It includes the IP address the request came from. Library owners do not see IP
            addresses; the LibraryHive team can.
          </li>
        </List>
      </Section>

      <Section id="walk-in" title="When a library owner adds you">
        <p>
          Owners can admit a student who walks in, before that student has an account. The owner enters your name and your phone
          number and/or email address, and we create a record for you without a password. We never match people by name. If you later
          sign up online with the same phone number or email, we do not link the two automatically. You must first prove the record is
          yours with a one-time code sent to your email, or a code the library owner gives you. Only then is the record turned into
          your account.
        </p>
        <p>
          The owner is expected to tell you that they are entering your details. <Todo>wording about how the student is informed and
          about the owner&apos;s responsibility for data they enter, to be agreed with the Terms of Service</Todo>
        </p>
      </Section>

      <Section id="who-sees" title="Who can see your information">
        <List>
          <li>
            <strong>You</strong> can see your own account, memberships, attendance and payments.
          </li>
          <li>
            <strong>A library owner</strong> can see the name, phone, email and exam of students who have a booking, membership,
            visit request or complaint with <em>their</em> library, together with that library&apos;s attendance and payment
            records. Owners cannot see other libraries&apos; records.
          </li>
          <li>
            <strong>The public</strong> sees a library&apos;s details, plans, photos, seat availability and, for each exam, only the
            number of members. They do not see who the members are.
          </li>
          <li>
            <strong>The LibraryHive team</strong> can see the data above to run the service and investigate problems.
          </li>
        </List>
      </Section>

      <Section id="location" title="Location">
        <p>
          <strong>Near-me search on the Discover page.</strong> If you press &quot;Use my location&quot;, your browser asks for your
          permission. If you allow it, your coordinates are placed in the web address of the Discover page (as <code>lat</code> and{" "}
          <code>lng</code>) and are sent to the LibraryHive server so that libraries can be sorted by distance. We do not save them to
          your account or in our database.
        </p>
        <p>Because the coordinates are in the page address:</p>
        <List>
          <li>they may appear in your browser&apos;s history, and</li>
          <li>anyone you send that address to will see them, so do not share the link if you do not want to share your location.</li>
        </List>
        <p>
          Our own application records each request with its path (for example <code>/api/v1/libraries/</code>) but not the part of
          the address after the question mark, and it is set up to hide coordinates if they ever appear in a log field. We have{" "}
          <strong>not yet checked</strong> how our hosting provider, the web server and the website host record web addresses, or how
          long they keep them. So we cannot promise that your coordinates are absent from those technical logs.{" "}
          <Todo>result of the hosting log check, and how long those logs are kept</Todo>
        </p>
        <p>
          <strong>A library&apos;s location.</strong> When a library owner sets the library&apos;s location on the map, or uses their
          device&apos;s current position to do so, those coordinates are saved as the library&apos;s location and are shown
          publicly. Owners should set the position of the library, not of their home.
        </p>
      </Section>

      <Section id="outside" title="Outside services your browser contacts">
        <p>
          The services below receive data <strong>directly from your browser</strong>, not through LibraryHive. They have their own
          privacy policies, which we do not control.
        </p>
        <List>
          <li>
            <strong>OpenStreetMap map tiles.</strong> The map on a library&apos;s page, and the owner&apos;s location picker, show
            map pictures loaded from OpenStreetMap&apos;s servers (<code>tile.openstreetmap.org</code>, run by the OpenStreetMap
            Foundation). Your browser asks that server for each piece of the map, so it receives your IP address, which part of the
            map you are looking at, and the address of our website (as the &quot;referrer&quot;). Our site adds no name or
            account details to these requests. Maps load only on those pages. The Discover page does not show a map. Map data ©
            OpenStreetMap contributors. We may change the map provider later and will update this page if we do.{" "}
            <Todo>provider decision for the period after the pilot</Todo>
          </li>
          <li>
            <strong>Nominatim place search (library owners only).</strong> When an owner types a place name in the location picker and
            presses the search button (or Enter), the text they typed is sent from their browser to OpenStreetMap&apos;s Nominatim
            service, with their IP address and our website address as the referrer. Nothing is sent while typing, and nothing from
            their LibraryHive account is included. Searches are limited to India.
          </li>
          <li>
            <strong>Razorpay (online payments).</strong> When you pay online, the Razorpay payment window opens inside LibraryHive.
            You enter your card, UPI or bank details to Razorpay, not to us. Razorpay tells our server whether the payment worked, and
            our server checks that message before confirming your seat. Razorpay may keep the payer contact details it receives; its
            privacy policy applies to that. <Todo>Razorpay merchant account and live-mode status; LibraryHive has so far tested online
            payment only in Razorpay&apos;s test mode</Todo>
          </li>
        </List>
        <p>We do not use advertising or analytics trackers on LibraryHive.</p>
      </Section>

      <Section id="cookies" title="Cookies and sign-in">
        <p>
          When you sign in we keep a short-lived access token in your browser&apos;s memory only. We also set one cookie that keeps
          you signed in for up to 7 days. It is an &quot;HttpOnly&quot; cookie that is sent only over secure connections and only
          to our sign-in address, so scripts on the page cannot read it. Signing out removes it.
        </p>
      </Section>

      <Section id="security" title="How we protect your information">
        <List>
          <li>Passwords are stored in scrambled (hashed) form. One-time codes are stored hashed, expire, and lock after repeated wrong attempts.</li>
          <li>Every request is checked on our server for who you are and what you may see. Owners can reach only their own library&apos;s records.</li>
          <li>Payments are confirmed only after our server verifies a cryptographic signature from Razorpay, never because the browser says it paid.</li>
          <li>Our application logs mask email addresses and phone numbers and leave out passwords, tokens and codes.</li>
        </List>
        <p>No system is perfectly secure, and we cannot guarantee that your information will never be exposed.</p>
      </Section>

      <Section id="keeping" title="How long we keep information, and your requests">
        <p>
          LibraryHive does not yet have a self-service way to delete or download your data. To ask us to correct your details, close
          your account or give you a copy of your information, contact us (below). We will handle these requests by hand. We close an
          account by deactivating it, and we may need to keep payment and membership history where it is needed for financial or
          legal records.
        </p>
        <p>
          <Todo>how long each kind of data is kept, whether deletion is offered after an account is closed, and the timeframe in
          which requests are answered</Todo>
        </p>
      </Section>

      <Section id="contact" title="Contact us about privacy">
        <List>
          <li>
            Email: <Todo>privacy or support email address</Todo>
          </li>
          <li>
            Grievance contact: <Todo>name and contact details, if one is required</Todo>
          </li>
        </List>
        <p>
          <Todo>review by someone qualified against the Digital Personal Data Protection Act, 2023 and its rules, including
          consent wording at sign-up and for owner-assisted admission</Todo>
        </p>
      </Section>

      <p className="text-sm text-slate-600">
        <Link href="/" className="underline underline-offset-2 hover:text-slate-900">
          Back to home
        </Link>
      </p>
    </article>
  );
}
