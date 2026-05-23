# My-Bachelor-Thesis
This repo contains my bachelor's project code, documentation, datasets used, diagrams' source code, and a readme file.

# AI-Integrated ERP Accounts Payable Automation

This repository outlines the implementation and deployment of a decoupled Accounts Payable (AP) automation artifact. The architecture serves as a bridge between advanced cognitive artificial intelligence (AI) functions and strict enterprise databases. By utilizing a lightweight Python API gateway, the system processes highly unstructured external inputs into rigorous, schema-compliant enterprise records without requiring modifications to the underlying ERP codebase.

## System Architecture Overview

The solution is divided into four distinct layers, enabling autonomous end-to-end processing while maintaining strict financial governance through a Human-in-the-Loop (HITL) failsafe.

1. **Ingestion Layer (Gmail IMAP):** An asynchronous Python listener polls a designated inbox for vendor invoices, extracting plain text bodies or attached PDF documents into a temporary local staging directory.
2. **Cognitive Extraction Layer (Gemini 2.5 Flash):** The AI replaces traditional OCR, multimodally extracting vendor data, dates (ISO), and totals. It outputs a purely formatted JSON payload and acts as the primary governance filter by calculating a mathematical extraction confidence score.
3. **Middleware (Python API Gateway):** A centralized script operating in VS Code that orchestrates the flow and enforces a strict **90.0% confidence threshold** for automated ledger entries.
4. **ERP Layer (Salesforce):** The System of Record. Clean payloads (Scores >= 90%) are mapped to a custom `Vendor_Invoice__c` object. Flagged documents (Scores < 90%) are routed to a low-code Lightning Flow dashboard for human review, providing real-time Explainable AI (XAI) insights.

---

## Part 1: Prerequisites & Infrastructure Provisioning

To replicate this architecture, you must provision three separate cloud environments and securely feed their credentials into the Python middleware.

### 1. The Ingestion Node (Gmail)
* Create a dedicated Google Account (e.g., `enterprise.ap.gateway@gmail.com`).
* Enable **2-Step Verification** on this account.
* Generate an **App Password**. Save this 16-character string; standard passwords will block Python IMAP connections.

### 2. The Cognitive Node (Google AI Studio)
* Navigate to Google AI Studio and generate a **Gemini API Key**. 
* Ensure your account has access to the `gemini-2.5-flash` multimodal endpoint.

### 3. The ERP Node (Salesforce)
* Provision a free Salesforce Developer Edition Org.
* Navigate to your personal settings and generate a **Security Token**. (Salesforce APIs require this token to be appended to your password).

---

## Part 2: ERP Schema Configuration (Salesforce Data Model)
Before the Python gateway can push data, the foundational relational database must be built inside Salesforce.


**1. Create the Invoice Object (`Vendor_Invoice__c`)**
* Create a new Custom Object named `Vendor_Invoice`.
* Add Custom Fields:
    * `Vendor_Name__c` (Text)
    * `Total_Amount__c` (Currency)
    * `Invoice_Date__c` (Date)
    * `Processing_Status__c` (Picklist: *Manual Review Required*, *AI Approved*)

**2. Create the Quarantine Firewall Object (`Invoice_Exception__c`)**
This object holds the quarantined payloads (Scores < 90%) to prevent anomalous data from polluting the master ledger.

* Create a new Custom Object named `Invoice_Exception`.
* Add the following Custom Fields *(Note: Vendor is kept as text here in case the AI hallucinates a vendor that does not exist in the database)*:
  * `Vendor_Name__c` (Text)
  * `Extracted_Total_Amount__c` (Currency)
  * `Extracted_Invoice_Date__c` (Date)
  * `AI_Confidence_Score__c` (Number, 3, 1)
  * `AI_Warning_Reason__c` (Long Text Area)
  * `Exception_Status__c` (Picklist: *Pending Review*, *Approved - Ready to Post*, *Rejected*)

---

## Part 3: Human-in-the-Loop Presentation Layer (Salesforce UI)
This step constructs the Accounts Payable Exception Dashboard, providing XAI insights to the accounting team without requiring custom Apex code.

### 1. Configure the Quarantine Queue
* Navigate to the `Invoice_Exception__c` tab in the Salesforce frontend.
* Create a New List View named **"Action Required: Quarantined Invoices"**.
* Add a filter: `Exception_Status__c` EQUALS `Pending Review`.
* Select fields to display: Exception ID, Extracted Vendor Name, AI Confidence Score, and AI Warning Reason.

### 2. Create the Resolution Flow
* Navigate to **Setup > Flows** and build a **Screen Flow**.
* Add a Screen element to display the `AI_Warning_Reason__c` to the accountant.
* Add input fields for the user to type in the corrected Vendor, Date, and Amount.
* Add a **Create Records** element: When the accountant clicks "Approve & Post", the Flow automatically creates a clean `Vendor_Invoice__c` record and changes the current `Invoice_Exception__c` status to *Resolved*.
---

## Part 4: Middleware & Environment Setup (Python)

### 1. Local Environment Setup
Clone this repository into your local Visual Studio Code (VS Code) environment.
Install the required libraries using your terminal:
```bash
pip install google-genai simple-salesforce imaplib email python-dotenv

---

* Below are the lines needed to be populated with your own credentials in order to succesfully test the code:

# Gmail IMAP Credentials
GMAIL_USER=your_ap_inbox@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# Google Gemini API
GEMINI_API_KEY=your_google_ai_studio_key

# Salesforce ERP Credentials
SF_USERNAME=your_salesforce_admin_username
SF_PASSWORD=your_salesforce_password
SF_SECURITY_TOKEN=your_salesforce_security_token
SF_DOMAIN=login username