from simple_salesforce import Salesforce
from google import genai
from google.genai import types
import json
import imaplib
import email
import time
import os

# LAYER 1: ERP CREDENTIALS (SALESFORCE)          CREDENTIALS!!!
SF_USERNAME = ''
SF_PASSWORD = ''
SF_SECURITY_TOKEN = ''
GEMINI_API_KEY = ''

client = genai.Client(api_key=GEMINI_API_KEY)

def extract_invoice_data(payload, is_pdf=False):
    prompt = """
    You are an enterprise Accounts Payable AI. Extract the invoice details from the provided document or text.
    Return ONLY a valid JSON object mapped exactly to these keys:
    - "vendor_name": string
    - "invoice_number": string
    - "invoice_date": string (must be formatted strictly as YYYY-MM-DD)
    - "total_amount": float (numbers only, no currency symbols or commas)
    - "confidence_score": integer (between 0 and 100, representing how confident you are in the extraction)
    - "warning_reason": string (If confidence is below 90, briefly explain the ambiguity or missing data. Otherwise, return an empty string)
    """
    
    if is_pdf:
        print(f"Layer 3: Uploading PDF to Gemini Vision Engine...")
        uploaded_file = client.files.upload(file=payload)
        contents_to_send = [uploaded_file, prompt]
    else:
        print("Layer 3: Gemini AI Engine processing unstructured text...")
        contents_to_send = [f"Email content:\n{payload}\n", prompt]
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents_to_send,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    
    extracted_data = json.loads(response.text)
    print(f"AI Extraction Complete: {extracted_data}")
    return extracted_data


# LAYER 4 & 2: GOVERNANCE & API GATEWAY
def process_invoice(payload, is_pdf=False):
    print("\n--- INITIATING AP WORKFLOW ---")
    extracted_data = extract_invoice_data(payload, is_pdf)
    try:
        sf = Salesforce(
            username=SF_USERNAME, 
            password=SF_PASSWORD, 
            security_token=SF_SECURITY_TOKEN, 
            domain='login'
        )
    except Exception as e:
        print(f"SALESFORCE AUTH ERROR: {e}")
        return
    
    print(f"Layer 4: Validating AI Confidence Score: {extracted_data['confidence_score']}%")
    
    # EXCEPTION PATH
    if extracted_data['confidence_score'] < 90:
        print("EXCEPTION: AI Confidence too low. Routing to Exception Dashboard...")
        try:
            exception_record = sf.Invoice_Exception__c.create({
                'Vendor_Name__c': extracted_data.get('vendor_name', 'Unknown'),
                'Invoice_Number__c': extracted_data.get('invoice_number', 'Unknown'),
                'Extracted_Total__c': extracted_data.get('total_amount', 0.0),
                'AI_Confidence_Score__c': extracted_data.get('confidence_score', 0),
                'AI_Warning_Reason__c': extracted_data.get('warning_reason', 'Data ambiguity detected.'),
                'Status__c': 'Pending Review'
            })
            print(f"EXCEPTION QUEUED! Pushed to Screen Flow. Record ID: {exception_record['id']}")
        except Exception as e:
            print(f"EXCEPTION ROUTING ERROR: {e}")
        return 
        
    # SUCCESS PATH
    print("Validation Passed. Routing to Layer 1 ERP Ledger...")
    try:
        new_record = sf.Vendor_Invoice__c.create({
            'Vendor_Name__c': extracted_data.get('vendor_name'),
            'Invoice_Date__c': extracted_data.get('invoice_date'),
            'Total_Amount__c': extracted_data.get('total_amount'),
            'Processing_Status__c': 'AI Approved'
        })
        print(f"SUCCESS! Invoice Auto-Posted in Salesforce. Record ID: {new_record['id']}")
        
    except Exception as e:
        print(f"INTEGRATION ERROR: {e}")


# # LAYER 2: THE EVENT LISTENER (IMAP PULL)                CREDENTIALS!!!
GMAIL_USER = ''
GMAIL_APP_PASSWORD = ''

def listen_for_invoices():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    mail.select("inbox")
    status, messages = mail.search(None, "UNSEEN")
    email_ids = messages[0].split()

    if email_ids:
        print(f"\n[{time.strftime('%H:%M:%S')}] SYSTEM TRIGGER: New email detected! Analyzing payload...")
        for e_id in email_ids:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    pdf_path = None
                    body_text = ""
                    
                    # Traverse the email to find PDFs or text
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                            
                        # Check for PDF attachment
                        filename = part.get_filename()
                        if filename and filename.lower().endswith('.pdf'):
                            pdf_path = os.path.join(os.getcwd(), filename)
                            with open(pdf_path, 'wb') as f:
                                f.write(part.get_payload(decode=True))
                            print(f"Attachment '{filename}' downloaded locally.")
                            break # We found the invoice, stop looking
                            
                        # Fallback: grab text if no attachment
                        if part.get_content_type() == "text/plain" and not pdf_path:
                            body_text = part.get_payload(decode=True).decode(errors='ignore')
                    
                    # Route to the appropriate pipeline
                    if pdf_path:
                        process_invoice(pdf_path, is_pdf=True)
                        os.remove(pdf_path) # Clean up the local folder
                        print(f"Local file '{filename}' deleted to maintain security.")
                    elif body_text:
                        process_invoice(body_text, is_pdf=False)
            
            mail.store(e_id, '+FLAGS', '\\Seen')
            print("Email marked as read. Loop complete.")
            
    mail.logout()

# THE CONTINUOUS EXECUTION LOOP
if __name__ == "__main__":
    print("========================================")
    print(" AP MULTIMODAL GATEWAY ONLINE & WAITING")
    print(f" Monitoring: {GMAIL_USER}")
    print("========================================")
    
    while True:
        try:
            listen_for_invoices()
            time.sleep(10)
        except Exception as e:
            print(f"Listener Error: {e}")
            time.sleep(10)