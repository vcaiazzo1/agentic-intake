import json
import random
from datetime import datetime, timedelta

names = [
    "Alice Johnson", "Bob Martinez", "Carol Smith", "David Lee", "Emma Wilson",
    "Frank Brown", "Grace Kim", "Henry Davis", "Isabelle Nguyen", "James Taylor",
    "Karen White", "Liam Harris", "Mia Thompson", "Noah Garcia", "Olivia Anderson",
    "Paul Jackson", "Quinn Robinson", "Rachel Clark", "Samuel Lewis", "Tara Walker",
    "Umar Hall", "Victoria Allen", "William Young", "Xena King", "Yusuf Wright",
    "Zoe Scott", "Aaron Hill", "Bella Green", "Carlos Adams", "Diana Baker",
    "Ethan Nelson", "Fiona Carter", "George Mitchell", "Hannah Perez", "Ivan Roberts",
    "Julia Turner", "Kevin Phillips", "Laura Campbell", "Marcus Parker", "Nina Evans",
    "Oscar Edwards", "Patricia Collins", "Quincy Stewart", "Rosa Sanchez", "Steven Morris",
    "Teresa Rogers", "Ulrich Reed", "Vera Cook", "Wayne Morgan", "Xandra Bell",
]

def fake_email(name):
    parts = name.lower().split()
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "proton.me"]
    return f"{parts[0]}.{parts[1]}{random.randint(10,99)}@{random.choice(domains)}"

def random_timestamp():
    base = datetime(2025, 1, 1)
    offset = timedelta(days=random.randint(0, 480), hours=random.randint(0, 23), minutes=random.randint(0, 59))
    return (base + offset).strftime("%Y-%m-%dT%H:%M:%S")

bug_reports = [
    {
        "subject": "App crashes on startup after latest update",
        "message": "Ever since I updated to version 3.2.1 yesterday, the app crashes immediately on startup. I've tried reinstalling it twice but the problem persists. My device is running iOS 17.4. This is really affecting my work — please fix this ASAP.",
    },
    {
        "subject": "Export to PDF button does nothing",
        "message": "The 'Export to PDF' button stopped working about two days ago. When I click it, a loading spinner appears briefly and then disappears without downloading anything. I've tested in Chrome and Edge and the issue is the same in both.",
    },
    {
        "subject": "Login fails with correct credentials",
        "message": "I've been locked out of my account since this morning. I'm 100% sure my password is correct because I use a password manager. The error message just says 'Invalid credentials' with no further explanation. I tried resetting my password but the reset email never arrived.",
    },
    {
        "subject": "Dashboard charts not loading — blank white boxes",
        "message": "All of the charts on my dashboard are showing as blank white boxes. The numbers in the summary cards look correct, but the visual graphs just won't render. This started happening after I switched browsers to Firefox 124.",
    },
    {
        "subject": "Notifications not being delivered",
        "message": "I set up email alerts for new orders three weeks ago and they worked perfectly until last Friday. Now I'm not receiving any notifications even though orders are coming in — I can see them in the portal. Please investigate.",
    },
    {
        "subject": "Search returns no results for any query",
        "message": "The search bar has completely stopped working. No matter what I type — even the exact title of a document I can see on screen — it returns 'No results found.' This started around 10 AM today. Other team members are experiencing the same issue.",
    },
    {
        "subject": "File upload stuck at 0% progress",
        "message": "I can't upload any files to the system. The progress bar appears and immediately freezes at 0%. I've tried files of different sizes and formats (PDF, DOCX, PNG) and none of them work. My internet connection is fine — other uploads elsewhere work normally.",
    },
    {
        "subject": "Two-factor authentication code always rejected",
        "message": "My 2FA codes are being rejected even though the timer hasn't expired. I'm using Google Authenticator and the time on my phone is correct. This started happening after I got a new phone and re-scanned the QR code. I'm completely unable to log in.",
    },
    {
        "subject": "Date picker selects wrong date",
        "message": "When I click on a date in the calendar picker, it saves a date one day earlier than what I selected. For example, clicking May 15 saves May 14. This is causing incorrect scheduling across all my bookings and I've had to go back and manually correct dozens of entries.",
    },
    {
        "subject": "CSV import silently drops rows",
        "message": "I imported a CSV with 500 records and only 487 appeared in the system. There was no error message or warning. Looking at the missing rows, I can't find any obvious formatting difference. I need to know which rows were skipped and why.",
    },
    {
        "subject": "Mobile app freezes when switching tabs",
        "message": "On my Android phone (Pixel 8, Android 14), the app freezes for 5–10 seconds every time I switch between the Home, Reports, and Settings tabs. It doesn't crash but it becomes completely unresponsive during that time. This makes the app nearly unusable.",
    },
    {
        "subject": "Password reset link expired immediately",
        "message": "I clicked the password reset link within 30 seconds of receiving the email and it said the link had already expired. I tried three more times with the same result. I'm now locked out of my account and can't get back in.",
    },
    {
        "subject": "Invoice totals calculated incorrectly",
        "message": "The invoice generation feature is applying the discount percentage before adding tax instead of after, resulting in incorrect totals. For a $1,000 order with 10% discount and 8% tax, it should come to $972 but the system is showing $979.20. This is causing billing discrepancies.",
    },
    {
        "subject": "Dark mode makes text unreadable",
        "message": "After enabling dark mode, several text fields render dark gray text on a dark background — almost impossible to read. This affects the notes section, the tag editor, and the custom fields panel. The rest of the UI looks fine in dark mode.",
    },
    {
        "subject": "Webhook events arriving out of order",
        "message": "Our webhook receiver is getting 'order.completed' events before 'order.created' events for the same order ID. This is breaking our downstream processing. We've confirmed the issue is on your side by checking timestamps — they're being dispatched in the wrong sequence.",
    },
]

feature_requests = [
    {
        "subject": "Add bulk delete option to inbox",
        "message": "Could you please add a 'Select All' checkbox and a bulk delete button to the inbox? Right now I have to delete messages one by one, which is very time-consuming when I need to clear hundreds of old notifications. This would save me a lot of time every week.",
    },
    {
        "subject": "Support dark mode on the web app",
        "message": "I'd love to see a dark mode option for the web application. I use your platform for long sessions late at night and the bright white interface is hard on my eyes. The mobile app already has this feature — it would be great to have it on desktop too.",
    },
    {
        "subject": "Allow recurring invoices to be scheduled",
        "message": "Please add support for recurring invoices that are automatically generated and sent on a schedule (weekly, monthly, annually). I have several retainer clients and manually creating the same invoice each month is tedious. QuickBooks has this feature and it's something I really miss.",
    },
    {
        "subject": "Add Slack integration for notifications",
        "message": "It would be extremely useful to receive important alerts directly in our Slack workspace instead of only by email. I often miss emails but I always see Slack messages. Even a simple webhook integration where I can choose which event types to forward would be a great start.",
    },
    {
        "subject": "Export reports to Excel format",
        "message": "The current export options only include CSV and PDF. Could you add native Excel (.xlsx) export? CSV loses formatting like column widths and merged cells, which means extra work cleaning up the data before I can share it with management.",
    },
    {
        "subject": "Add keyboard shortcuts for common actions",
        "message": "As a power user, I'd love to have keyboard shortcuts for the most common actions — creating a new record, saving, navigating between tabs, and opening the search bar. This would significantly speed up my workflow. Even a basic set to start would be wonderful.",
    },
    {
        "subject": "Allow custom fields on customer profiles",
        "message": "We track several pieces of information about our customers that don't fit in the standard fields — things like their preferred contact time and their industry vertical. It would be really helpful to be able to add custom fields to the customer profile page.",
    },
    {
        "subject": "Add a mobile app for Android",
        "message": "You currently have an iOS app but no Android version. Our whole team uses Android devices and we'd love to be able to manage things on the go. Even a lightweight version covering the most important features would make a big difference for us.",
    },
    {
        "subject": "Show last login date on user management page",
        "message": "As an admin, I'd like to see the last login date for each user on the user management page. This would help me identify inactive accounts and manage licences more effectively. Right now I have no way to know who is actively using the platform.",
    },
    {
        "subject": "Two-panel view to compare records side by side",
        "message": "It would be very helpful to be able to open two records in a split-screen view to compare them directly. I frequently need to check differences between two versions of a document or two customer accounts, and constantly switching tabs is inefficient.",
    },
]

billing_issues = [
    {
        "subject": "Charged twice for the same invoice",
        "message": "I was charged twice for invoice #INV-20481 on April 3rd — both charges of $149 appear on my credit card statement. I only authorized one payment. Please refund the duplicate charge and confirm this won't happen again.",
    },
    {
        "subject": "Subscription upgraded without my consent",
        "message": "My plan was upgraded from Basic to Pro last week and I was charged $89 more than expected. I never requested an upgrade. Please downgrade my account back to Basic and refund the difference.",
    },
    {
        "subject": "Promo code not applied at checkout",
        "message": "I used the promo code SAVE20 at checkout but the discount was never applied — I was charged the full price of $199. The code is valid according to your website and doesn't expire until June 30th. Please apply the discount retroactively or issue a credit.",
    },
    {
        "subject": "Still being charged after cancellation",
        "message": "I cancelled my subscription on March 15th and received a confirmation email, but I was still charged $59 on April 1st. This is now the second charge after my cancellation. Please stop all future billing and refund the post-cancellation charges.",
    },
    {
        "subject": "Invoice shows wrong company name",
        "message": "Our company recently changed its legal name from Apex Solutions Inc. to Apex Group LLC. The last three invoices still show the old name, which is causing problems with our accounting department. Please update our billing details and reissue the most recent invoice.",
    },
    {
        "subject": "VAT not included on invoices — need it for tax purposes",
        "message": "I'm based in Germany and all of our vendor invoices need to include a VAT line item for our tax reporting. Your invoices don't show VAT at all, which means I can't submit them to our finance team. Please update the invoices for our account to include German VAT.",
    },
    {
        "subject": "Annual plan charged monthly instead",
        "message": "I signed up for the annual plan at $499/year but I'm being charged $49/month instead, which would come to $588 — $89 more per year. This doesn't match what was shown on the pricing page when I signed up. Please correct this.",
    },
    {
        "subject": "Refund request for unused seats",
        "message": "We purchased 20 seats in January but only ended up using 12. We'd like a partial refund for the 8 unused seats for the remaining 8 months of our contract. I've already removed those users from the account. Can you process this?",
    },
    {
        "subject": "Payment method update not saving",
        "message": "I've been trying to update my credit card for two days. Every time I enter the new card details and click Save, I get a generic error message and the old (expired) card remains on file. Because of this, my last payment failed and I'm worried my account will be suspended.",
    },
    {
        "subject": "Unclear charge labeled 'PLATFORM FEE' on statement",
        "message": "There's an unexpected charge of $25 labeled 'PLATFORM FEE' on my latest invoice that wasn't on any previous invoices and wasn't mentioned when I signed up. I can't find any information about this fee in my account settings. Please explain what this charge is for.",
    },
]

general_questions = [
    {
        "subject": "How do I add team members to my account?",
        "message": "I just upgraded to the Team plan and I'd like to add my two colleagues. Could you walk me through how to invite new users? I've looked through the Settings menu but I can't find an obvious 'Invite' button. A step-by-step guide or a link to documentation would be really helpful.",
    },
    {
        "subject": "What file formats does the import support?",
        "message": "I have customer data in various formats — Excel, CSV, and a Google Sheets export. Before I spend time converting everything, could you tell me exactly which file formats the import tool supports? Also, is there a maximum file size limit?",
    },
    {
        "subject": "Can I integrate with Zapier?",
        "message": "We use Zapier extensively to automate workflows between different tools. I couldn't find your platform listed in the Zapier app directory. Do you have a Zapier integration, or is there another way to connect to third-party services via an API or webhooks?",
    },
    {
        "subject": "How do I downgrade my subscription plan?",
        "message": "I'm currently on the Business plan but I don't use most of the advanced features and would like to move down to the Pro plan to reduce my monthly costs. Is it possible to downgrade mid-billing cycle, and if so, will I receive a prorated credit?",
    },
    {
        "subject": "What is your data retention policy?",
        "message": "Before we commit to using your platform for sensitive client data, our security team needs to understand your data retention policy. Specifically: how long is data stored after an account is closed, and do you offer options for data deletion on request?",
    },
    {
        "subject": "How do I generate a monthly usage report?",
        "message": "My manager has asked for a monthly report showing how many transactions were processed through the platform. I found the Reports section but there are a lot of options and I'm not sure which report type to use. Can you point me to the right report or explain how to configure it?",
    },
    {
        "subject": "Is there a limit on the number of projects I can create?",
        "message": "I'm planning a large rollout where I'll need to create around 200 separate projects for different client accounts. I want to make sure there's no cap on the number of projects before I start. If there is a limit on my current plan, what would I need to upgrade to?",
    },
    {
        "subject": "How does the auto-archive feature work?",
        "message": "I noticed there's an auto-archive setting in my account but the description is a bit vague. Could you explain what exactly gets archived, when it happens, and whether archived items can be recovered? I want to make sure I don't accidentally lose any active records.",
    },
    {
        "subject": "Do you offer single sign-on (SSO)?",
        "message": "Our company uses Okta for identity management and we require SSO for all SaaS tools. Do you support SAML 2.0 or OIDC SSO? If so, which plans include it and where can I find the setup instructions?",
    },
    {
        "subject": "What happens to my data if I cancel?",
        "message": "I'm evaluating whether to continue my subscription and I want to understand what happens to my data if I decide to cancel. Will I still be able to export everything before my access ends? How long do you keep the data after cancellation?",
    },
]

ambiguous_requests = [
    {
        "subject": "Things have been a bit off lately",
        "message": "I'm not sure if it's just me but everything just feels a bit slower than it used to be. Pages take a little longer to load, or maybe they don't — it's hard to say. It's not broken, but something feels different. Has anything changed on your end recently? Just wanted to flag it in case it's useful.",
    },
    {
        "subject": "Not happy with recent changes",
        "message": "The last update changed the layout and I don't like how the new dashboard looks. It's also missing a button that I used every day and now I can't find it anywhere. I don't know if it was removed or just moved. Can someone help me or explain the reasoning behind these changes?",
    },
    {
        "subject": "Need more flexibility with the system",
        "message": "Your platform is good but it feels quite rigid in some areas. For example, I can't organize things the way I want, and some of the default settings don't make sense for my workflow. I'm not sure if there are hidden settings I'm missing or if these are actual limitations. Either way, I need more control.",
    },
    {
        "subject": "Something's wrong with my account",
        "message": "I logged in today and things look different from how I left them. Some records that I'm sure I created are gone or maybe they're just in a different place. I don't know if I did something accidentally or if there was a system issue. Can you check my account activity?",
    },
    {
        "subject": "Your system doesn't work well for our use case",
        "message": "We've been using your tool for six months and it mostly works, but we're running into limitations. Our process requires steps that your workflow doesn't support natively, so we've been hacking around it. I'm reaching out because I'm not sure if we're using it wrong, if there are features we're missing, or if we genuinely need something that doesn't exist yet.",
    },
]

all_templates = (
    [("bug_report", t) for t in bug_reports] +
    [("feature_request", t) for t in feature_requests] +
    [("billing_issue", t) for t in billing_issues] +
    [("general_question", t) for t in general_questions] +
    [("ambiguous", t) for t in ambiguous_requests]
)

requests = []
for i, (category, template) in enumerate(all_templates, start=1):
    name = names[i - 1]
    requests.append({
        "id": i,
        "name": name,
        "email": fake_email(name),
        "category": category,
        "subject": template["subject"],
        "message": template["message"],
        "timestamp": random_timestamp(),
    })

random.shuffle(requests)
for i, req in enumerate(requests, start=1):
    req["id"] = i

with open("requests.json", "w", encoding="utf-8") as f:
    json.dump(requests, f, indent=2, ensure_ascii=False)

print(f"Generated {len(requests)} requests and saved to requests.json")
