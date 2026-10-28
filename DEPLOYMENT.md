# OAuth Setup Guide for z3n-ai-mixed307 Environment

**Amazon Connect Instance**: `arn:aws:connect:eu-west-2:228449306526:instance/78309a83-1cf4-4ade-9dbd-dc15fa4af1b1`  
**Zendesk URL**: `z3n-ai-mixed307.zendesk.com`  
**AWS Region**: `eu-west-2` (London)  
**AWS Account**: `228449306526`

**Date**: 2026-07-24  
**Author**: Richard Uzzell

---

## Overview

This guide walks through setting up OAuth authentication for the **Search Open Tickets Lambda** in your z3n-ai-mixed307 Zendesk environment.

---

## Phase 1: Create Zendesk OAuth Client

### Step 1.1: Access Zendesk Admin Center

1. **Go to**: https://z3n-ai-mixed307.zendesk.com/admin/
2. **Log in** with admin credentials
3. **Navigate to**: Apps and integrations > APIs > OAuth Clients
4. **Click**: "Add OAuth client" (top right)

---

### Step 1.2: Configure OAuth Client

Fill in these exact values:

| Field | Value |
|-------|-------|
| **Client Name** | `Amazon Connect Search Tickets Lambda` |
| **Description** | `OAuth client for searching open tickets from Amazon Connect contact flows` |
| **Company** | Your company name |
| **Logo** | (Optional) |
| **Unique Identifier** | (Auto-generated - save this!) |
| **Secret** | ⚠️ **SHOWN ONLY ONCE** - Copy immediately! |
| **Redirect URLs** | Leave empty (not needed for client credentials flow) |

---

### Step 1.3: Set Required Scopes

Select these scopes:

- ✅ `read` - Read access
- ✅ `write` - Write access (needed for ticket updates)

**Or more granular**:
- ✅ `tickets:read` - Read tickets
- ✅ `users:read` - Read user information (for phone lookup)

---

### Step 1.4: Save Credentials

After clicking "Save", **immediately copy**:

1. **Client Identifier (Client ID)**: 
   ```
   Example: amazon_connect_search_tickets_lambda
   ```
   **Your value**: `____________________________________`

2. **Secret (Client Secret)**: ⚠️ **Shown only once!**
   ```
   Example: 9d64fe6b5376feabceeadd075fff39434973f45d800981c9bb491d84e44e5a20
   ```
   **Your value**: `____________________________________`

3. **Subdomain**: (Already known)
   ```
   z3n-ai-mixed307
   ```

**⚠️ CRITICAL**: Save these values now - you'll need them in the next step!

---

## Phase 2: Create AWS Secrets Manager Secret

### Step 2.1: Navigate to Secrets Manager

1. **Go to AWS Console**: https://console.aws.amazon.com
2. **Switch to region**: `eu-west-2` (London) - **CRITICAL: Same region as your Connect instance**
3. **Navigate to**: Secrets Manager
4. **Click**: "Store a new secret"

---

### Step 2.2: Configure Secret

**Step 1 - Choose secret type**:
- Select: **"Other type of secret"**
- Select: **"Plaintext"** tab
- **Paste this JSON** (replace with your actual values from Step 1.4):

```json
{
  "client_id": "YOUR_CLIENT_ID_FROM_ZENDESK",
  "client_secret": "YOUR_CLIENT_SECRET_FROM_ZENDESK",
  "subdomain": "z3n-ai-mixed307",
  "access_token": "",
  "token_expiry": 0
}
```

**Example with placeholder values**:
```json
{
  "client_id": "amazon_connect_search_tickets_lambda",
  "client_secret": "9d64fe6b5376feabceeadd075fff39434973f45d800981c9bb491d84e44e5a20",
  "subdomain": "z3n-ai-mixed307",
  "access_token": "",
  "token_expiry": 0
}
```

**Encryption key**: Select `aws/secretsmanager` (default)

**Click "Next"**

---

**Step 2 - Configure secret**:

| Field | Value |
|-------|-------|
| **Secret name** | `zendesk/oauth/z3n-ai-mixed307` |
| **Description** | `Zendesk OAuth credentials for z3n-ai-mixed307 - Search Open Tickets Lambda` |
| **Tags** (Optional) | `Environment=Production`, `Service=AmazonConnect`, `Zendesk=z3n-ai-mixed307` |

**Click "Next"**

---

**Step 3 - Configure rotation**:
- **Disable automatic rotation** (Zendesk doesn't support automated OAuth rotation)
- **Click "Next"**

---

**Step 4 - Review**:
- Review settings
- **Click "Store"**

---

### Step 2.3: Copy Secret ARN

After creating the secret:

1. **Click on secret name**: `zendesk/oauth/z3n-ai-mixed307`
2. **Copy the Secret ARN** - it will look like:
   ```
   arn:aws:secretsmanager:eu-west-2:228449306526:secret:zendesk/oauth/z3n-ai-mixed307-AbCdEf
   ```
3. **Save this ARN** - you'll need it for IAM policies

**Your Secret ARN**: `____________________________________`

---

## Phase 3: Create Lambda Function

### Step 3.1: Prepare Lambda Deployment Package

On your local machine:

```bash
# Create deployment directory
mkdir ~/lambda-search-tickets
cd ~/lambda-search-tickets

# Copy Lambda function
cp ~/Documents/search_open_tickets_lambda.py lambda_function.py

# Copy OAuth module
cp ~/Documents/zendesk_oauth.py .

# Install requests library
pip3 install requests -t .

# Create deployment package
zip -r search-tickets-lambda.zip .
```

**Result**: You now have `search-tickets-lambda.zip` ready to upload

---

### Step 3.2: Create IAM Role for Lambda

**Option A: AWS Console**

1. **Go to IAM Console**: https://console.aws.amazon.com/iam/
2. **Navigate to**: Roles > Create role
3. **Select trusted entity**: AWS service > Lambda
4. **Click "Next"**

**Attach policies**:
- ✅ `AWSLambdaBasicExecutionRole` (for CloudWatch Logs)

**Click "Next"**

**Role name**: `SearchTicketsLambda-z3n-ai-mixed307-role`

**Click "Create role"**

---

**Add inline policy for Secrets Manager**:

1. **Click on the role** you just created
2. **Click "Add permissions" > "Create inline policy"**
3. **Select JSON tab**
4. **Paste this policy** (use your Secret ARN from Step 2.3):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ZendeskOAuthSecretsAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:UpdateSecret"
      ],
      "Resource": "arn:aws:secretsmanager:eu-west-2:228449306526:secret:zendesk/oauth/z3n-ai-mixed307-*"
    }
  ]
}
```

**Policy name**: `SecretsManagerAccessForZendesk`

**Click "Create policy"**

---

**Copy Role ARN**:
- After creating the role, copy the Role ARN:
  ```
  arn:aws:iam::228449306526:role/SearchTicketsLambda-z3n-ai-mixed307-role
  ```

**Your Role ARN**: `____________________________________`

---

### Step 3.3: Create Lambda Function

**Navigate to Lambda Console**: https://eu-west-2.console.aws.amazon.com/lambda/

**Click "Create function"**

| Field | Value |
|-------|-------|
| **Option** | Author from scratch |
| **Function name** | `SearchOpenTicketsLambda-z3n-ai-mixed307` |
| **Runtime** | Python 3.12 |
| **Architecture** | x86_64 |
| **Execution role** | Use an existing role |
| **Existing role** | `SearchTicketsLambda-z3n-ai-mixed307-role` (from Step 3.2) |

**Click "Create function"**

---

### Step 3.4: Upload Lambda Code

1. **In the Lambda function page**, scroll to "Code source"
2. **Click "Upload from" > ".zip file"**
3. **Select** `search-tickets-lambda.zip` from Step 3.1
4. **Click "Save"**
5. **Wait for upload to complete**

---

### Step 3.5: Configure Lambda Settings

**Configuration tab > General configuration > Edit**:

| Setting | Value |
|---------|-------|
| **Memory** | `256 MB` |
| **Timeout** | `15 seconds` |
| **Ephemeral storage** | `512 MB` (default) |

**Click "Save"**

---

**Configuration tab > Environment variables > Edit**:

Click "Add environment variable" and add:

| Key | Value |
|-----|-------|
| `ZENDESK_OAUTH_SECRET_NAME` | `zendesk/oauth/z3n-ai-mixed307` |
| `SEARCH_DAYS_BACK` | `7` |
| `MAX_TICKETS_RETURN` | `5` |
| `LOG_LEVEL` | `INFO` |

**Click "Save"**

---

### Step 3.6: Copy Lambda ARN

From the Lambda function page, copy the **Function ARN** (top right):

```
arn:aws:lambda:eu-west-2:228449306526:function:SearchOpenTicketsLambda-z3n-ai-mixed307
```

**Your Lambda ARN**: `____________________________________`

---

## Phase 4: Test Lambda Function

### Step 4.1: Create Test Event

In Lambda console:

1. **Click "Test" tab**
2. **Click "Create new event"**
3. **Event name**: `TestCustomerSearch`
4. **Event JSON**:

```json
{
  "customer_phone": "+447425162654",
  "search_days_back": 7,
  "max_tickets": 5
}
```

**Replace** `+447425162654` with a real customer phone number from your Zendesk

**Click "Save"**

---

### Step 4.2: Run Test

1. **Click "Test"** button
2. **Wait for execution** (should take 2-5 seconds)
3. **Check results**:

**Expected Success Response**:
```json
{
  "success": true,
  "customer_phone": "+447425162654",
  "search_days_back": 7,
  "open_tickets_count": 2,
  "tickets": [
    {
      "ticket_id": "12345",
      "subject": "Billing inquiry",
      "intent": "billing_dispute",
      "summary": "Customer reported..."
    }
  ],
  "ai_agent_context": "Customer has 2 open tickets: ..."
}
```

**If you get errors**, check:
- CloudWatch Logs for detailed error messages
- Secret ARN in environment variable matches Secrets Manager
- IAM role has Secrets Manager permissions
- OAuth credentials in secret are correct

---

## Phase 5: Grant Amazon Connect Permissions

### Step 5.1: Add Lambda Permission for Amazon Connect

**Option A: AWS CLI** (if you have CLI access):

```bash
aws lambda add-permission \
  --function-name SearchOpenTicketsLambda-z3n-ai-mixed307 \
  --statement-id AllowAmazonConnectInvoke \
  --action lambda:InvokeFunction \
  --principal connect.amazonaws.com \
  --source-account 228449306526 \
  --source-arn arn:aws:connect:eu-west-2:228449306526:instance/78309a83-1cf4-4ade-9dbd-dc15fa4af1b1 \
  --region eu-west-2
```

---

**Option B: AWS Console** (if no CLI access):

1. **In Lambda console**, go to your function
2. **Click "Configuration" tab**
3. **Click "Permissions" (left sidebar)**
4. **Scroll to "Resource-based policy statements"**
5. **Click "Add permissions"**
6. **Select "AWS service"**
7. **Configure**:

| Field | Value |
|-------|-------|
| **Service** | Other |
| **Statement ID** | `AllowAmazonConnectInvoke` |
| **Principal** | `connect.amazonaws.com` |
| **Source ARN** | `arn:aws:connect:eu-west-2:228449306526:instance/78309a83-1cf4-4ade-9dbd-dc15fa4af1b1` |
| **Action** | `lambda:InvokeFunction` |

**Click "Save"**

---

### Step 5.2: Add Lambda to Amazon Connect

1. **Go to Amazon Connect Console**: https://eu-west-2.console.aws.amazon.com/connect/
2. **Select your instance**: Click instance alias or ID
3. **Click "Contact flows" (left sidebar)**
4. **Scroll to "AWS Lambda"**
5. **Select your function** from dropdown:
   ```
   SearchOpenTicketsLambda-z3n-ai-mixed307
   ```
6. **Click "Add Lambda Function"**

**Confirmation**: You should see the function listed under "Lambda functions"

---

## Phase 6: Integrate with Amazon Connect Contact Flow

### Step 6.1: Create Test Contact Flow

1. **Go to Amazon Connect dashboard**: https://[your-instance-alias].my.connect.aws/
2. **Navigate to**: Routing > Contact flows
3. **Click "Create contact flow"**
4. **Name**: `Test Search Open Tickets`

---

### Step 6.2: Add Invoke Lambda Block

**Drag blocks onto canvas**:

1. **Invoke AWS Lambda function** block
2. **Set contact attributes** block
3. **Play prompt** block

---

**Configure "Invoke AWS Lambda function" block**:

| Setting | Value |
|---------|-------|
| **Select a function** | `SearchOpenTicketsLambda-z3n-ai-mixed307` |
| **Timeout (seconds)** | `15` |
| **Function input parameters** | (Leave empty - uses customer phone automatically) |
| **Destination key** | `OpenTickets` |

**Connect**:
- Success → Set contact attributes
- Error → Play prompt (error message)

---

**Configure "Set contact attributes" block**:

Add these attributes (for testing):

| Destination key | Type | Attribute |
|----------------|------|-----------|
| `TicketCount` | External | `OpenTickets.open_tickets_count` |
| `FirstTicketID` | External | `OpenTickets.tickets[0].ticket_id` |
| `FirstTicketSubject` | External | `OpenTickets.tickets[0].subject` |
| `FirstTicketIntent` | External | `OpenTickets.tickets[0].intent` |
| `AIContext` | External | `OpenTickets.ai_agent_context` |

---

**Configure "Play prompt" block** (for testing):

- **Type**: Text-to-speech
- **Text**: 
  ```
  You have $.Attributes.TicketCount open tickets. 
  The first ticket is about $.Attributes.FirstTicketSubject.
  ```

---

### Step 6.3: Test the Contact Flow

1. **Save and Publish** the contact flow
2. **Assign a phone number** to this contact flow
3. **Call the number** from a phone that has open tickets in Zendesk
4. **Listen to the prompt** - it should read your ticket count and subject

---

## Phase 7: Verification Checklist

### ✅ Zendesk OAuth Client
- [ ] Created OAuth client in z3n-ai-mixed307.zendesk.com
- [ ] Saved Client ID
- [ ] Saved Client Secret
- [ ] Set scopes: `read`, `write` (or `tickets:read`, `users:read`)

### ✅ AWS Secrets Manager
- [ ] Created secret in `eu-west-2` region
- [ ] Secret name: `zendesk/oauth/z3n-ai-mixed307`
- [ ] Secret contains valid JSON with client_id, client_secret, subdomain
- [ ] Copied Secret ARN

### ✅ Lambda Function
- [ ] Created Lambda in `eu-west-2` region
- [ ] Uploaded code package with `zendesk_oauth.py`
- [ ] Set environment variable: `ZENDESK_OAUTH_SECRET_NAME`
- [ ] IAM role has Secrets Manager permissions
- [ ] Lambda timeout set to 15 seconds
- [ ] Tested Lambda successfully

### ✅ Amazon Connect Integration
- [ ] Added Lambda permission for Connect to invoke
- [ ] Added Lambda to Connect instance
- [ ] Created test contact flow
- [ ] Tested end-to-end flow
- [ ] Lambda returns ticket data correctly

---

## Troubleshooting

### Error: "Access Denied" when Lambda reads secret

**Cause**: IAM role lacks Secrets Manager permission

**Fix**:
1. Go to IAM > Roles > `SearchTicketsLambda-z3n-ai-mixed307-role`
2. Check inline policy includes `secretsmanager:GetSecretValue`
3. Verify Resource ARN matches your secret ARN

---

### Error: "Invalid client credentials" (401)

**Cause**: Wrong Client ID or Secret in Secrets Manager

**Fix**:
1. Go to Secrets Manager > `zendesk/oauth/z3n-ai-mixed307`
2. Click "Retrieve secret value"
3. Verify `client_id` and `client_secret` match Zendesk OAuth client
4. Check for extra spaces or formatting issues

---

### Error: "ResourceNotFoundException: Secret not found"

**Cause**: Secret name mismatch or wrong region

**Fix**:
1. Verify Lambda is in `eu-west-2` (same as secret)
2. Check environment variable `ZENDESK_OAUTH_SECRET_NAME` = `zendesk/oauth/z3n-ai-mixed307`
3. Verify secret exists in Secrets Manager

---

### No tickets returned (but tickets exist)

**Cause**: Phone number format mismatch or tickets too old

**Fix**:
1. Check Zendesk user profile has phone number in correct format
2. Increase `SEARCH_DAYS_BACK` environment variable
3. Check CloudWatch Logs for Zendesk search query
4. Test with a ticket created today

---

## CloudWatch Logs

To view Lambda execution logs:

1. **Go to CloudWatch**: https://eu-west-2.console.aws.amazon.com/cloudwatch/
2. **Navigate to**: Logs > Log groups
3. **Find**: `/aws/lambda/SearchOpenTicketsLambda-z3n-ai-mixed307`
4. **Click on latest log stream**
5. **Check for errors**

**Useful log entries**:
- "Searching for open tickets for phone: +44..."
- "Zendesk search query: type:ticket..."
- "Found X tickets for +44..."
- "Successfully obtained access token"

---

## Next Steps

### 1. Integrate with AI Agent

Update your AI Agent prompt with ticket context:

```
You are a customer service agent for z3n-ai-mixed307.

{{AIContext}}

Available tickets:
{{#each OpenTickets.tickets}}
- Ticket {{ticket_id}}: {{subject}} (Intent: {{intent}})
{{/each}}

Ask the customer which ticket they are calling about.
```

---

### 2. Create Screen Pop Lambda

Create a second Lambda to fetch full ticket details for agent screen pop:

```python
def get_ticket_details_lambda(ticket_id):
    """Fetch complete ticket including comments, custom fields"""
    # Future implementation
```

---

### 3. Monitor Usage

Set up CloudWatch alarms:

1. **Lambda errors** > 5 in 5 minutes
2. **Lambda duration** > 10 seconds (p99)
3. **Secrets Manager API calls** (for cost monitoring)

---

## Summary

Your environment is now configured:

| Component | Value |
|-----------|-------|
| **Zendesk** | z3n-ai-mixed307.zendesk.com |
| **AWS Region** | eu-west-2 (London) |
| **Secret Name** | `zendesk/oauth/z3n-ai-mixed307` |
| **Lambda Name** | `SearchOpenTicketsLambda-z3n-ai-mixed307` |
| **Connect Instance** | `78309a83-1cf4-4ade-9dbd-dc15fa4af1b1` |

**Status**: Ready for production use ✅

---

**Document Version**: 1.0  
**Last Updated**: 2026-07-24  
**Environment**: z3n-ai-mixed307 (Production)
