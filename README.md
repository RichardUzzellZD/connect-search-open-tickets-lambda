# Search Open Tickets Lambda - Amazon Connect AI Agent Integration

**Purpose**: Search Zendesk for customer's recent open tickets and provide context to AI Agent for authentication and routing.

**Author**: Richard Uzzell  
**Date**: 2026-07-24  
**Version**: 1.0

---

## Use Case

```
Customer calls Amazon Connect
         ↓
Lambda searches Zendesk for customer's open tickets (by phone number)
         ↓
Returns ticket IDs, summaries, and intents
         ↓
AI Agent uses ticket info to:
  1. Authenticate customer ("Which ticket are you calling about?")
  2. Route to correct open ticket
  3. Provide context-aware responses
```

---

## What This Lambda Does

1. **Receives customer phone number** from Amazon Connect
2. **Searches Zendesk** for open tickets (last 7 days by default)
3. **Extracts ticket details**:
   - Ticket ID
   - Subject
   - Status (open, pending, etc.)
   - Priority
   - **Summary** (first 200 chars of description)
   - **Intent** (inferred from tags/subject: billing_dispute, technical_support, etc.)
   - Tags
4. **Returns formatted data** for AI Agent consumption

---

## Example Response

```json
{
  "success": true,
  "customer_phone": "+447425162654",
  "search_days_back": 7,
  "open_tickets_count": 2,
  "tickets": [
    {
      "ticket_id": "12345",
      "subject": "Billing inquiry - duplicate charge",
      "status": "open",
      "priority": "normal",
      "created_at": "2024-07-10T14:30:00Z",
      "updated_at": "2024-07-11T10:15:00Z",
      "summary": "Customer reported duplicate charge of £50 on their account on July 8th. Customer provided transaction reference...",
      "intent": "billing_dispute",
      "tags": ["billing", "duplicate_charge", "urgent"],
      "url": "https://your-subdomain.zendesk.com/api/v2/tickets/12345.json"
    },
    {
      "ticket_id": "12346",
      "subject": "Cannot access online banking",
      "status": "pending",
      "priority": "high",
      "created_at": "2024-07-12T09:15:00Z",
      "updated_at": "2024-07-13T14:20:00Z",
      "summary": "Customer unable to log in to online banking since yesterday. Reset password but still getting error message...",
      "intent": "technical_support",
      "tags": ["online_banking", "login_issue"],
      "url": "https://your-subdomain.zendesk.com/api/v2/tickets/12346.json"
    }
  ],
  "ai_agent_context": "Customer has 2 open ticket(s): Ticket 12345: Billing inquiry - duplicate charge (Intent: billing_dispute, Status: open); Ticket 12346: Cannot access online banking (Intent: technical_support, Status: pending)"
}
```

---

## Intent Detection

The Lambda automatically infers customer intent from ticket tags and subject:

| Intent | Keywords Detected |
|--------|------------------|
| `billing_dispute` | billing, charge, payment, refund, invoice, duplicate, overcharge |
| `technical_support` | login, access, password, error, broken, not working, unable to |
| `account_inquiry` | account, balance, statement, information, update, change |
| `fraud_alert` | fraud, suspicious, unauthorized, stolen, lost card |
| `service_request` | request, new, setup, activate, upgrade, downgrade |
| `complaint` | complaint, unhappy, dissatisfied, poor service, escalate |
| `cancellation` | cancel, close, terminate, stop, end service |
| `general_inquiry` | Default if no match |

**Use in AI Agent**: Intent helps the AI Agent understand why the customer opened the ticket and provide context-aware responses.

---

## Amazon Connect Integration

### 1. Invoke Lambda Block Configuration

In your Amazon Connect contact flow:

**Block**: Invoke AWS Lambda function  
**Function ARN**: `arn:aws:lambda:REGION:ACCOUNT:function:SearchOpenTicketsLambda`  
**Timeout**: 8 seconds (default) or 15 seconds (recommended)

**Parameters** (Optional):
- `search_days_back` = `7` (default: 7 days)
- `max_tickets` = `5` (default: 5 tickets)

**Destination Key**: `OpenTickets` (stores response in $.External.OpenTickets)

---

### 2. Access Results in Contact Flow

After invoking the Lambda, results are available at:

```
$.External.OpenTickets.success             → true/false
$.External.OpenTickets.open_tickets_count  → 2
$.External.OpenTickets.tickets[0].ticket_id → "12345"
$.External.OpenTickets.tickets[0].subject   → "Billing inquiry..."
$.External.OpenTickets.tickets[0].intent    → "billing_dispute"
$.External.OpenTickets.ai_agent_context     → "Customer has 2 open..."
```

---

### 3. Check Contact Attributes in Contact Flow

**Check Attribute Block** to branch based on ticket count:

**Condition 1**: `$.External.OpenTickets.open_tickets_count` > 0
- **Action**: Route to AI Agent with ticket context

**Condition 2**: `$.External.OpenTickets.open_tickets_count` = 0
- **Action**: Route to standard IVR (no open tickets)

---

### 4. Pass to AI Agent

**Set Contact Attributes Block** - Store ticket info for AI Agent:

```
ticket_count      = $.External.OpenTickets.open_tickets_count
ticket_id_1       = $.External.OpenTickets.tickets[0].ticket_id
ticket_subject_1  = $.External.OpenTickets.tickets[0].subject
ticket_intent_1   = $.External.OpenTickets.tickets[0].intent
ticket_id_2       = $.External.OpenTickets.tickets[1].ticket_id
ticket_subject_2  = $.External.OpenTickets.tickets[1].subject
ticket_intent_2   = $.External.OpenTickets.tickets[1].intent
ai_context        = $.External.OpenTickets.ai_agent_context
```

**Agent Instructions Block** - Add to AI Agent prompt:

```
You are a customer service agent. The customer has called about an existing support ticket.

{{ai_context}}

Available tickets:
1. Ticket {{ticket_id_1}}: {{ticket_subject_1}} (Intent: {{ticket_intent_1}})
2. Ticket {{ticket_id_2}}: {{ticket_subject_2}} (Intent: {{ticket_intent_2}})

First, ask the customer which ticket they are calling about. Use the ticket subjects to help them identify the correct one.

Once confirmed, retrieve full ticket details and assist the customer.
```

---

## AI Agent Authentication Flow

### Suggested Conversation Flow

**AI Agent**: "Hello! I can see you have 2 open support tickets with us. Are you calling about your billing inquiry from July 10th, or the online banking access issue from July 12th?"

**Customer**: "The billing one"

**AI Agent**: "Thank you for confirming. I can see ticket 12345 regarding a duplicate charge of £50. Let me pull up the details and help you with that."

*(AI Agent then invokes another Lambda to fetch full ticket details using ticket_id)*

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `ZENDESK_OAUTH_SECRET_NAME` | AWS Secrets Manager secret name | `zendesk/oauth/connect-lambda` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `SEARCH_DAYS_BACK` | Number of days to search back | `7` |
| `MAX_TICKETS_RETURN` | Maximum tickets to return | `5` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## IAM Permissions

### Lambda Execution Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ZendeskOAuthSecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:UpdateSecret"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:zendesk/oauth/connect-lambda-*"
    },
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

## Deployment

### Prerequisites

1. **AWS Secrets Manager secret** with Zendesk OAuth credentials (see OAuth migration guide)
2. **zendesk_oauth.py module** (package with Lambda or use Lambda Layer)
3. **requests library** (package with Lambda or use Lambda Layer)

### Option 1: Deployment Package

```bash
# Create deployment directory
mkdir lambda-package
cd lambda-package

# Copy Lambda function
cp search_open_tickets_lambda.py lambda_function.py

# Copy OAuth module
cp zendesk_oauth.py .

# Install requests
pip install requests -t .

# Create zip
zip -r search-open-tickets-lambda.zip .

# Upload to AWS Lambda
aws lambda create-function \
  --function-name SearchOpenTicketsLambda \
  --runtime python3.12 \
  --role arn:aws:iam::ACCOUNT:role/LambdaExecutionRole \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://search-open-tickets-lambda.zip \
  --timeout 15 \
  --memory-size 256 \
  --environment Variables="{ZENDESK_OAUTH_SECRET_NAME=zendesk/oauth/connect-lambda,SEARCH_DAYS_BACK=7,MAX_TICKETS_RETURN=5}"
```

### Option 2: Lambda Layer (Recommended)

```bash
# Create layer with dependencies (see OAuth migration guide)
# Then create Lambda with layer attached

aws lambda create-function \
  --function-name SearchOpenTicketsLambda \
  --runtime python3.12 \
  --role arn:aws:iam::ACCOUNT:role/LambdaExecutionRole \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function-code.zip \
  --layers arn:aws:lambda:REGION:ACCOUNT:layer:zendesk-oauth-layer:1 \
  --timeout 15 \
  --memory-size 256 \
  --environment Variables="{ZENDESK_OAUTH_SECRET_NAME=zendesk/oauth/connect-lambda}"
```

---

## Amazon Connect Permissions

Grant Amazon Connect permission to invoke the Lambda:

```bash
aws lambda add-permission \
  --function-name SearchOpenTicketsLambda \
  --statement-id AllowAmazonConnectInvoke \
  --action lambda:InvokeFunction \
  --principal connect.amazonaws.com \
  --source-account ACCOUNT_ID \
  --source-arn arn:aws:connect:REGION:ACCOUNT:instance/INSTANCE_ID
```

---

## Testing

### Test Event 1: Simple Format

```json
{
  "customer_phone": "+447425162654",
  "search_days_back": 7,
  "max_tickets": 5
}
```

### Test Event 2: Amazon Connect Format

```json
{
  "Details": {
    "ContactData": {
      "CustomerEndpoint": {
        "Address": "+447425162654"
      },
      "Attributes": {
        "search_days_back": "7",
        "max_tickets": "5"
      }
    }
  }
}
```

### Expected Success Response

```json
{
  "success": true,
  "customer_phone": "+447425162654",
  "search_days_back": 7,
  "open_tickets_count": 2,
  "tickets": [...],
  "ai_agent_context": "Customer has 2 open ticket(s): ..."
}
```

### Expected No Tickets Response

```json
{
  "success": true,
  "customer_phone": "+447425162654",
  "search_days_back": 7,
  "open_tickets_count": 0,
  "tickets": [],
  "ai_agent_context": "Customer has no open tickets in the last 7 days"
}
```

---

## Zendesk Search Query

The Lambda uses this Zendesk search query:

```
type:ticket status<solved created>2024-07-17 "+447425162654"
```

**Breakdown**:
- `type:ticket` - Search only tickets (not users, organizations)
- `status<solved` - Status is NOT solved (includes: new, open, pending, hold)
- `created>2024-07-17` - Created after specified date (7 days back)
- `"+447425162654"` - Requester phone number matches

**Note**: Zendesk searches the requester's phone field. Phone number must be stored in the ticket requester profile.

---

## Troubleshooting

### No tickets found (but tickets exist)

**Possible causes**:
1. **Phone number format mismatch** - Zendesk stores phone as `+44 7425 162654`, Lambda searches `+447425162654`
   - **Solution**: Lambda normalizes phone (removes spaces/dashes) but Zendesk may not match
   - **Fix**: Ensure Zendesk stores phone in consistent format

2. **Tickets older than search window** - Default is 7 days
   - **Solution**: Increase `SEARCH_DAYS_BACK` environment variable

3. **Tickets are solved/closed** - Search only includes open tickets
   - **Solution**: Update search query to include solved tickets (not recommended for this use case)

4. **Phone not associated with ticket requester**
   - **Solution**: Ensure customer's Zendesk user profile has phone number

### Lambda timeout

**Cause**: Zendesk search taking too long

**Solution**: 
- Increase Lambda timeout to 15-20 seconds
- Reduce `SEARCH_DAYS_BACK` to narrow search
- Reduce `MAX_TICKETS_RETURN` to limit results

### OAuth errors

**Cause**: Expired token or invalid credentials

**Solution**: See OAuth migration troubleshooting guide

---

## Advanced: Multiple Phone Number Formats

If your Zendesk stores phone numbers in multiple formats, update the search query:

```python
# Search for multiple phone formats
phone_formats = [
    customer_phone,                      # +447425162654
    customer_phone.replace('+', ''),     # 447425162654
    customer_phone.replace('+44', '0')   # 07425162654 (UK)
]

# Build OR query
search_query = f'type:ticket status<solved created>{date_str} ('
search_query += ' OR '.join([f'"{phone}"' for phone in phone_formats])
search_query += ')'
```

---

## Next Steps

### Complementary Lambda: Get Full Ticket Details

Once AI Agent confirms which ticket the customer is calling about, create a second Lambda to fetch full ticket details:

```python
def get_ticket_details(ticket_id):
    """
    Fetch complete ticket details including:
    - All comments/conversation history
    - Custom fields
    - Assignee information
    - Related tickets
    """
    # Implementation for future Lambda
```

### Store Ticket ID in Contact Attributes

After AI Agent confirms the ticket, store it:

```
confirmed_ticket_id = "12345"
confirmed_ticket_intent = "billing_dispute"
```

Use this in:
- Screen pop to agent desktop (open specific ticket)
- Contact Lens post-call analysis
- Zendesk ticket update (add call log)

---

## Related Documentation

- [OAuth Migration Guide](zendesk-oauth-migration-guide.md)
- [Zendesk OAuth IAM Policy](zendesk-oauth-iam-policy.json)
- [OAuth Module Documentation](zendesk_oauth.py)

---

**Document Version**: 1.0  
**Last Updated**: 2026-07-24  
**Lambda Function**: search_open_tickets_lambda.py
