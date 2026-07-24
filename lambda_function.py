"""
AWS Lambda function to search Zendesk for open tickets by customer phone number.

This Lambda is designed for Amazon Connect AI Agent integration:
- Searches Zendesk for open tickets from the last 7 days
- Finds tickets associated with customer's phone number
- Returns ticket IDs, summaries, and intents for AI Agent authentication
- Uses OAuth 2.0 authentication

Use Case:
Customer calls Amazon Connect → Lambda searches their recent open tickets →
AI Agent uses ticket info to authenticate customer and route to correct ticket

Environment Variables Required:
- ZENDESK_OAUTH_SECRET_NAME: AWS Secrets Manager secret name (e.g., 'zendesk/oauth/connect-lambda')
- SEARCH_DAYS_BACK: Number of days to search back (default: 7)
- MAX_TICKETS_RETURN: Maximum tickets to return (default: 5)
- LOG_LEVEL: Logging level (default: INFO)

IAM Permissions Required:
- secretsmanager:GetSecretValue
- secretsmanager:UpdateSecret

Lambda Layer/Package Requirements:
- zendesk_oauth.py module
- requests library
- boto3 (included in Lambda runtime)

Returns:
{
    "success": true,
    "customer_phone": "+447425162654",
    "open_tickets_count": 2,
    "tickets": [
        {
            "ticket_id": "12345",
            "subject": "Billing inquiry - duplicate charge",
            "status": "open",
            "priority": "normal",
            "created_at": "2024-07-10T14:30:00Z",
            "summary": "Customer reported duplicate charge of £50 on their account...",
            "intent": "billing_dispute",
            "tags": ["billing", "duplicate_charge", "urgent"]
        },
        {
            "ticket_id": "12346",
            "subject": "Cannot access online banking",
            "status": "pending",
            "priority": "high",
            "created_at": "2024-07-12T09:15:00Z",
            "summary": "Customer unable to log in to online banking since yesterday...",
            "intent": "technical_support",
            "tags": ["online_banking", "login_issue"]
        }
    ],
    "ai_agent_context": "Customer has 2 open tickets: 12345 (billing dispute), 12346 (login issue)"
}

Author: Richard Uzzell
Date: 2026-07-24
Version: 1.0
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import quote

# Import OAuth module (must be packaged with Lambda or in Lambda Layer)
from zendesk_oauth import make_zendesk_request, get_zendesk_subdomain

# Set up logging
logger = logging.getLogger()
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logger.setLevel(log_level)

# Configuration
ZENDESK_OAUTH_SECRET_NAME = os.environ.get('ZENDESK_OAUTH_SECRET_NAME')
SEARCH_DAYS_BACK = int(os.environ.get('SEARCH_DAYS_BACK', '7'))
MAX_TICKETS_RETURN = int(os.environ.get('MAX_TICKETS_RETURN', '5'))


def extract_ticket_intent(ticket: Dict[str, Any]) -> str:
    """
    Extract or infer the intent/purpose from a ticket.

    Uses tags, subject, and description to determine intent.

    Args:
        ticket: Zendesk ticket object

    Returns:
        Intent string (e.g., 'billing_dispute', 'technical_support', 'account_inquiry')
    """
    subject = ticket.get('subject', '').lower()
    tags = [tag.lower() for tag in ticket.get('tags', [])]

    # Intent mapping based on common keywords
    intent_keywords = {
        'billing_dispute': ['billing', 'charge', 'payment', 'refund', 'invoice', 'duplicate', 'overcharge'],
        'technical_support': ['login', 'access', 'password', 'error', 'broken', 'not working', 'unable to'],
        'account_inquiry': ['account', 'balance', 'statement', 'information', 'update', 'change'],
        'fraud_alert': ['fraud', 'suspicious', 'unauthorized', 'stolen', 'lost card'],
        'service_request': ['request', 'new', 'setup', 'activate', 'upgrade', 'downgrade'],
        'complaint': ['complaint', 'unhappy', 'dissatisfied', 'poor service', 'escalate'],
        'cancellation': ['cancel', 'close', 'terminate', 'stop', 'end service']
    }

    # Check tags first (most reliable)
    for intent, keywords in intent_keywords.items():
        if any(keyword in tags for keyword in keywords):
            return intent

    # Check subject line
    for intent, keywords in intent_keywords.items():
        if any(keyword in subject for keyword in keywords):
            return intent

    # Default intent
    return 'general_inquiry'


def extract_ticket_summary(ticket: Dict[str, Any]) -> str:
    """
    Create a concise summary of the ticket for AI Agent context.

    Args:
        ticket: Zendesk ticket object

    Returns:
        Summary string (first 200 characters of description or subject)
    """
    # Try to get the first comment (description)
    description = ticket.get('description', '')

    if description:
        # Clean HTML tags if present
        import re
        clean_desc = re.sub('<[^<]+?>', '', description)
        clean_desc = clean_desc.strip()

        # Return first 200 characters
        if len(clean_desc) > 200:
            return clean_desc[:197] + '...'
        return clean_desc

    # Fallback to subject
    subject = ticket.get('subject', 'No description available')
    if len(subject) > 200:
        return subject[:197] + '...'
    return subject


def search_open_tickets_by_phone(customer_phone: str) -> List[Dict[str, Any]]:
    """
    Search Zendesk for open tickets associated with a customer's phone number.

    Args:
        customer_phone: Customer's phone number (E.164 format recommended, e.g., +447425162654)

    Returns:
        List of ticket dictionaries with relevant fields
    """
    try:
        logger.info(f"Searching for open tickets for phone: {customer_phone}")

        # Calculate date range (last N days)
        date_threshold = datetime.utcnow() - timedelta(days=SEARCH_DAYS_BACK)
        date_str = date_threshold.strftime('%Y-%m-%d')

        # Build Zendesk search query
        # Search for tickets where requester phone matches, status is open/pending, created in last N days
        search_query = f'type:ticket status<solved created>{date_str}'

        # Add phone number to query - Zendesk searches requester phone field
        # Try multiple formats (with/without +, with/without spaces)
        phone_normalized = customer_phone.replace(' ', '').replace('-', '')
        search_query += f' "{phone_normalized}"'

        logger.info(f"Zendesk search query: {search_query}")

        # Get subdomain
        subdomain = get_zendesk_subdomain(ZENDESK_OAUTH_SECRET_NAME)

        # URL encode the query
        encoded_query = quote(search_query)
        url = f"https://{subdomain}.zendesk.com/api/v2/search.json?query={encoded_query}&sort_by=created_at&sort_order=desc"

        logger.debug(f"Search URL: {url}")

        # Make OAuth-authenticated request
        # NOTE: Use 'read' scope for Search API access (not 'tickets:read users:read')
        response = make_zendesk_request(
            'GET',
            url,
            ZENDESK_OAUTH_SECRET_NAME,
            scopes='read',
            timeout=15
        )

        response.raise_for_status()
        search_results = response.json()

        tickets = search_results.get('results', [])
        total_count = search_results.get('count', 0)

        logger.info(f"Found {total_count} tickets for {customer_phone}")

        # Limit results
        if len(tickets) > MAX_TICKETS_RETURN:
            logger.info(f"Limiting results to {MAX_TICKETS_RETURN} tickets (found {len(tickets)})")
            tickets = tickets[:MAX_TICKETS_RETURN]

        return tickets

    except Exception as e:
        logger.error(f"Failed to search tickets: {str(e)}")
        raise


def format_tickets_for_ai_agent(tickets: List[Dict[str, Any]], customer_phone: str) -> Dict[str, Any]:
    """
    Format ticket data for Amazon Connect AI Agent consumption.

    Args:
        tickets: List of Zendesk ticket objects
        customer_phone: Customer's phone number

    Returns:
        Formatted response dictionary
    """
    formatted_tickets = []

    for ticket in tickets:
        formatted_ticket = {
            'ticket_id': str(ticket.get('id')),
            'subject': ticket.get('subject', 'No subject'),
            'status': ticket.get('status', 'unknown'),
            'priority': ticket.get('priority', 'normal'),
            'created_at': ticket.get('created_at'),
            'updated_at': ticket.get('updated_at'),
            'summary': extract_ticket_summary(ticket),
            'intent': extract_ticket_intent(ticket),
            'tags': ticket.get('tags', []),
            'url': ticket.get('url', '')
        }

        formatted_tickets.append(formatted_ticket)

    # Create AI Agent context string (for prompt injection)
    if formatted_tickets:
        context_parts = []
        for ticket in formatted_tickets:
            context_parts.append(
                f"Ticket {ticket['ticket_id']}: {ticket['subject']} (Intent: {ticket['intent']}, Status: {ticket['status']})"
            )
        ai_context = f"Customer has {len(formatted_tickets)} open ticket(s): " + "; ".join(context_parts)
    else:
        ai_context = "Customer has no open tickets in the last 7 days"

    response = {
        'success': True,
        'customer_phone': customer_phone,
        'search_days_back': SEARCH_DAYS_BACK,
        'open_tickets_count': len(formatted_tickets),
        'tickets': formatted_tickets,
        'ai_agent_context': ai_context
    }

    return response


def lambda_handler(event, context):
    """
    AWS Lambda handler for searching Zendesk open tickets by phone number.

    Expected event structure from Amazon Connect:
    {
        "Details": {
            "ContactData": {
                "CustomerEndpoint": {
                    "Address": "+447425162654"  # Customer phone number
                },
                "Attributes": {
                    "search_days_back": "7",      # Optional: override default
                    "max_tickets": "5"             # Optional: override default
                }
            }
        }
    }

    OR simple format for testing:
    {
        "customer_phone": "+447425162654",
        "search_days_back": 7,
        "max_tickets": 5
    }

    Returns:
    {
        "success": true,
        "customer_phone": "+447425162654",
        "open_tickets_count": 2,
        "tickets": [...],
        "ai_agent_context": "Customer has 2 open ticket(s): Ticket 12345: ..."
    }
    """
    try:
        # Validate environment variables
        if not ZENDESK_OAUTH_SECRET_NAME:
            logger.error("Missing required environment variable: ZENDESK_OAUTH_SECRET_NAME")
            return {
                'success': False,
                'error': 'Lambda misconfigured: Missing ZENDESK_OAUTH_SECRET_NAME'
            }

        # Extract customer phone from event
        customer_phone = None

        # Try Amazon Connect format first
        if 'Details' in event and 'ContactData' in event['Details']:
            contact_data = event['Details']['ContactData']
            customer_phone = contact_data.get('CustomerEndpoint', {}).get('Address')

            # Check for override parameters
            attributes = contact_data.get('Attributes', {})
            if 'search_days_back' in attributes:
                global SEARCH_DAYS_BACK
                SEARCH_DAYS_BACK = int(attributes['search_days_back'])
            if 'max_tickets' in attributes:
                global MAX_TICKETS_RETURN
                MAX_TICKETS_RETURN = int(attributes['max_tickets'])

        # Try simple format
        elif 'customer_phone' in event:
            customer_phone = event['customer_phone']
            if 'search_days_back' in event:
                SEARCH_DAYS_BACK = int(event['search_days_back'])
            if 'max_tickets' in event:
                MAX_TICKETS_RETURN = int(event['max_tickets'])

        if not customer_phone:
            logger.error("No customer phone number provided in event")
            return {
                'success': False,
                'error': 'Missing customer phone number in event'
            }

        logger.info(f"Processing ticket search for: {customer_phone} (last {SEARCH_DAYS_BACK} days, max {MAX_TICKETS_RETURN} tickets)")

        # Search Zendesk for open tickets
        tickets = search_open_tickets_by_phone(customer_phone)

        # Format response for AI Agent
        response = format_tickets_for_ai_agent(tickets, customer_phone)

        logger.info(f"Successfully found {response['open_tickets_count']} open tickets")
        logger.debug(f"Response: {json.dumps(response, indent=2)}")

        return response

    except Exception as e:
        logger.error(f"Unhandled exception in lambda_handler: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'customer_phone': customer_phone if 'customer_phone' in locals() else 'unknown'
        }


# For local testing
if __name__ == '__main__':
    import sys

    # Set up logging for local testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Mock event for testing
    test_event = {
        'customer_phone': '+447425162654',
        'search_days_back': 7,
        'max_tickets': 5
    }

    # Set environment variable for testing
    os.environ['ZENDESK_OAUTH_SECRET_NAME'] = 'zendesk/oauth/connect-lambda'

    print("=" * 80)
    print("Testing Zendesk Open Tickets Search Lambda")
    print("=" * 80)
    print(f"\nTest Event:")
    print(json.dumps(test_event, indent=2))
    print("\n" + "=" * 80)

    try:
        result = lambda_handler(test_event, None)
        print("\nResult:")
        print(json.dumps(result, indent=2))

        if result['success']:
            print("\n" + "=" * 80)
            print("✓ Test completed successfully")
            print(f"✓ Found {result['open_tickets_count']} open tickets")
            print(f"\n✓ AI Agent Context:")
            print(f"  {result['ai_agent_context']}")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("✗ Test failed")
            print(f"✗ Error: {result.get('error')}")
            print("=" * 80)
            sys.exit(1)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"✗ Test failed with exception: {str(e)}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)
