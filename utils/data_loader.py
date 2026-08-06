"""Data loading and preparation utilities."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib

@pd.api.extensions.register_dataframe_accessor("resolve")
class ResolveOneAccessor:
    """Custom pandas accessor for ResolveOne operations."""

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def mask_ids(self):
        """Hash sensitive IDs."""
        df = self._obj.copy()
        for col in ['client_id', 'card_id']:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(
                    lambda x: hashlib.sha256(x.encode()).hexdigest()[:8]
                )
        return df

def load_sample_data():
    """Load data dynamically from /home/labuser/Desktop/Persistent_Folder/Capstone/data/raw or fallback."""
    import os
    
    raw_dir = "data/raw"
    possible_files = [
        os.path.join(raw_dir, "transactions_data.csv"),
        os.path.join(raw_dir, "cards_data.csv"),
        "data/samples/sample_critical.csv",
        "data/samples/sample_10pct.csv"
    ]
    
    df = None
    for file_path in possible_files:
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, nrows=5000) # Load subset for fast UI performance
                break
            except Exception:
                continue
                
    if df is not None:
        # Standardize columns based on raw dataset structure
        rename_map = {
            'timestamp': 'date',
            'date_time': 'date',
            'transaction_date': 'date',
            'error_code': 'exception_type',
            'failure_reason': 'exception_type',
            'merchant_category': 'merchant_category',
            'masked_client_id': 'client_id',
            'masked_card_id': 'card_id',
            'transaction_amount': 'amount',
            'txn_amount': 'amount'
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        
        # Ensure date column exists and is parsed correctly
        date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]
        if date_cols and 'date' not in df.columns:
            df['date'] = pd.to_datetime(df[date_cols[0]], errors='coerce')
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        else:
            df['date'] = datetime.now() - timedelta(days=1)
            
        df['date'] = df['date'].fillna(datetime.now())

        # Ensure amount column exists and is numeric
        amount_cols = [c for c in df.columns if 'amount' in c.lower() or 'amt' in c.lower()]
        if amount_cols and 'amount' not in df.columns:
            df['amount'] = pd.to_numeric(df[amount_cols[0]], errors='coerce').fillna(0.0)
        elif 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        else:
            df['amount'] = np.random.uniform(10, 1000, len(df))

        # Fill/map required application schema fields if absent
        if 'exception_id' not in df.columns:
            df['exception_id'] = [f'EXC-{i:06d}' for i in range(len(df))]
        if 'transaction_id' not in df.columns:
            if 'txn_id' in df.columns:
                df['transaction_id'] = df['txn_id']
            else:
                df['transaction_id'] = [f'TXN-{i:08d}' for i in range(len(df))]
        if 'customer_name' not in df.columns:
            df['customer_name'] = 'Customer ' + df.index.astype(str)
        if 'priority' not in df.columns:
            priorities = ['Critical', 'High', 'Medium', 'Low']
            df['priority'] = np.random.choice(priorities, len(df))
        if 'status' not in df.columns:
            statuses = ['Pending', 'In Review', 'Resolved', 'Escalated']
            df['status'] = np.random.choice(statuses, len(df))
        if 'exception_type' not in df.columns:
            df['exception_type'] = 'TECHNICAL_GLITCH'
        if 'root_cause' not in df.columns:
            df['root_cause'] = 'System timeout'
        if 'business_impact' not in df.columns:
            df['business_impact'] = 'Medium'
        if 'assigned_team' not in df.columns:
            df['assigned_team'] = 'Team A'
        if 'department' not in df.columns:
            df['department'] = 'Payment Processing'
        if 'card_brand' not in df.columns:
            df['card_brand'] = 'Visa'
        if 'merchant_name' not in df.columns:
            df['merchant_name'] = 'Merchant ' + df.index.astype(str)
        if 'merchant_city' not in df.columns:
            df['merchant_city'] = 'New York'
        if 'currency' not in df.columns:
            df['currency'] = 'USD'

        return df
    else:
        return generate_mock_data()

def generate_mock_data():
    """Generate realistic mock data for demo."""
    np.random.seed(42)
    n_rows = 3126

    exception_types = [
        "INSUFFICIENT_BALANCE", "INSUFFICIENT_BALANCE", "INSUFFICIENT_BALANCE",
        "BAD_PIN", "BAD_PIN",
        "TECHNICAL_GLITCH", "TECHNICAL_GLITCH",
        "BAD_CARD_NUMBER",
        "BAD_CVV",
        "BAD_EXPIRATION",
        "BAD_ZIPCODE"
    ]

    statuses = ["Pending", "In Review", "Resolved", "Escalated"]
    priorities = ["Critical", "High", "Medium", "Low"]
    departments = ["Payment Processing", "Card Services", "Risk Management", "Customer Support"]
    teams = ["Team A", "Team B", "Team C", "Team D"]
    card_brands = ["Visa", "Mastercard", "American Express"]

    base_date = datetime.now() - timedelta(days=30)

    data = {
        'exception_id': [f'EXC-{i:06d}' for i in range(n_rows)],
        'transaction_id': [f'TXN-{i:08d}' for i in range(n_rows)],
        'client_id': np.random.randint(1000, 9999, n_rows),
        'card_id': np.random.randint(1, 6000, n_rows),
        'customer_name': [f'Customer {i}' for i in range(n_rows)],
        'amount': np.random.uniform(10, 5000, n_rows),
        'currency': ['USD'] * n_rows,
        'exception_type': np.random.choice(exception_types, n_rows),
        'priority': np.random.choice(priorities, n_rows, p=[0.15, 0.25, 0.35, 0.25]),
        'status': np.random.choice(statuses, n_rows, p=[0.3, 0.25, 0.35, 0.1]),
        'date': [base_date + timedelta(hours=i) for i in range(n_rows)],
        'root_cause': ['System timeout', 'Insufficient balance', 'Card issue', 'Network error', 'Validation failure'] * (n_rows // 5 + 1),
        'business_impact': ['High', 'Medium', 'Low'] * (n_rows // 3 + 1),
        'assigned_team': np.random.choice(teams, n_rows),
        'department': np.random.choice(departments, n_rows),
        'card_brand': np.random.choice(card_brands, n_rows),
        'merchant_name': [f'Merchant {i}' for i in range(n_rows)],
        'merchant_city': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'] * (n_rows // 5 + 1),
        'mcc_code': np.random.randint(1000, 9999, n_rows),
    }

    df = pd.DataFrame(data)
    return df

def get_exception_stats(df):
    """Calculate exception statistics."""
    if df.empty:
        return {
            'total': 0,
            'critical': 0,
            'resolved_today': 0,
            'avg_resolution_time': 0
        }

    today = pd.Timestamp.now().normalize()

    total = len(df)
    critical = len(df[df['priority'] == 'Critical'])
    resolved_today = len(df[(df['status'] == 'Resolved') & (df['date'] >= today)])

    # Mock average resolution time
    avg_resolution_time = np.random.randint(30, 300)

    return {
        'total': total,
        'critical': critical,
        'resolved_today': resolved_today,
        'avg_resolution_time': avg_resolution_time,
        'exception_types': df['exception_type'].nunique(),
        'pending': len(df[df['status'] == 'Pending']),
    }

def get_exception_by_id(df, exception_id):
    """Get exception details by ID."""
    record = df[df['exception_id'] == exception_id]
    if record.empty:
        return None
    return record.iloc[0]

def filter_exceptions(df, priority=None, status=None, exception_type=None, department=None, date_range=None):
    """Filter exceptions based on criteria."""
    filtered = df.copy()

    if priority:
        filtered = filtered[filtered['priority'].isin(priority)]

    if status:
        filtered = filtered[filtered['status'].isin(status)]

    if exception_type:
        filtered = filtered[filtered['exception_type'].isin(exception_type)]

    if department:
        filtered = filtered[filtered['department'].isin(department)]

    if date_range:
        start_date, end_date = date_range
        filtered = filtered[(filtered['date'] >= start_date) & (filtered['date'] <= end_date)]

    return filtered

def search_exceptions(df, query):
    """Search exceptions by text."""
    if not query:
        return df

    query = query.lower()
    mask = (
        df['exception_id'].astype(str).str.lower().str.contains(query) |
        df['transaction_id'].astype(str).str.lower().str.contains(query) |
        df['customer_name'].astype(str).str.lower().str.contains(query) |
        df['merchant_name'].astype(str).str.lower().str.contains(query) |
        df['exception_type'].astype(str).str.lower().str.contains(query)
    )
    return df[mask]

def get_exception_timeline(exception_id):
    """Get timeline for exception investigation."""
    base_time = datetime.now()

    timeline = [
        {
            'time': (base_time - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
            'event': 'Exception Detected',
            'actor': 'System',
            'details': 'Transaction failed with insufficient balance'
        },
        {
            'time': (base_time - timedelta(hours=1.5)).strftime('%Y-%m-%d %H:%M:%S'),
            'event': 'Exception Queued',
            'actor': 'System',
            'details': 'Exception added to resolution queue'
        },
        {
            'time': (base_time - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'event': 'AI Analysis Started',
            'actor': 'ResolveOne AI',
            'details': 'Automated investigation initiated'
        },
        {
            'time': (base_time - timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S'),
            'event': 'Recommendation Generated',
            'actor': 'ResolveOne AI',
            'details': 'AI recommends manual verification + customer contact'
        },
        {
            'time': (base_time - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
            'event': 'Assigned to Team',
            'actor': 'System',
            'details': 'Assigned to Payment Processing Team A'
        },
    ]

    return timeline

def get_ai_recommendation(exception_type, priority):
    """Generate AI recommendation for exception."""
    recommendations = {
        'INSUFFICIENT_BALANCE': {
            'resolution': 'Contact customer to verify account status and recent activity',
            'confidence': 0.95,
            'estimated_time': '5-10 minutes',
            'next_steps': [
                'Send account balance notification',
                'Offer instant deposit option',
                'Flag for compliance review if suspicious'
            ]
        },
        'BAD_PIN': {
            'resolution': 'Initiate PIN reset workflow and send verification code',
            'confidence': 0.92,
            'estimated_time': '3-5 minutes',
            'next_steps': [
                'Send reset PIN SMS',
                'Create temporary access token',
                'Monitor for re-attempts'
            ]
        },
        'TECHNICAL_GLITCH': {
            'resolution': 'Retry transaction and escalate to engineering if failure persists',
            'confidence': 0.88,
            'estimated_time': '10-15 minutes',
            'next_steps': [
                'Attempt automatic retry',
                'Check system health metrics',
                'Escalate to engineering if needed'
            ]
        },
        'BAD_CARD_NUMBER': {
            'resolution': 'Request card reissuance and update customer payment method',
            'confidence': 0.98,
            'estimated_time': '2-3 days',
            'next_steps': [
                'Block current card',
                'Initiate reissuance process',
                'Notify customer'
            ]
        },
        'BAD_CVV': {
            'resolution': 'Require card re-authentication and security review',
            'confidence': 0.96,
            'estimated_time': '5-10 minutes',
            'next_steps': [
                'Flag for fraud review',
                'Send verification email',
                'Lock account temporarily'
            ]
        },
        'BAD_EXPIRATION': {
            'resolution': 'Update card expiration date or request new card',
            'confidence': 0.99,
            'estimated_time': '1-2 minutes',
            'next_steps': [
                'Check card database',
                'Send card update reminder',
                'Offer expedited replacement'
            ]
        },
        'BAD_ZIPCODE': {
            'resolution': 'Request address verification and update customer profile',
            'confidence': 0.85,
            'estimated_time': '5 minutes',
            'next_steps': [
                'Send address verification email',
                'Allow manual override',
                'Flag for compliance'
            ]
        }
    }

    return recommendations.get(exception_type, {
        'resolution': 'Manual review required',
        'confidence': 0.70,
        'estimated_time': '15-30 minutes',
        'next_steps': ['Escalate to supervisor', 'Review all transaction details']
    })

def get_ai_chat_responses(question):
    """Get AI assistant chat responses."""
    responses = {
        'why': 'Based on my analysis: This transaction failed due to insufficient balance in the customer\'s account. The account balance of $523.45 was below the required minimum for this $750 transaction. I recommend notifying the customer and offering instant deposit options.',
        'similar': 'I found 47 similar cases in the past 7 days:\n\n• 31 cases: Insufficient balance (same customer segments)\n• 12 cases: Technical glitches during peak hours\n• 4 cases: PIN validation failures\n\nTechnical glitches show higher resolution success when retried within 5 minutes.',
        'next': 'Recommended action plan:\n1. ✓ Send account balance alert (45% resolve themselves)\n2. ✓ Offer expedited deposit option (70% conversion)\n3. ✓ If no response in 2 hours, escalate to customer service\n4. Monitor for account status changes',
        'policy': 'According to policy EXC-2024-001 (Insufficient Balance):\n\n• Resolution SLA: 24 hours\n• Escalation criteria: After 4 hours without customer response\n• Authority level: Team Lead approval required\n• Audit trail: All actions must be logged\n\nThis exception falls under Standard tier.',
        'approval': 'Current approval status:\n✓ AI Analysis: Approved (95% confidence)\n✓ Compliance: Pending review\n⏳ Manager: Awaiting approval\n✗ Legal: Not yet reviewed\n\nI recommend: Proceed with customer contact while awaiting manager approval.'
    }

    question_lower = question.lower()

    if 'why' in question_lower or 'reason' in question_lower or 'cause' in question_lower:
        return responses['why']
    elif 'similar' in question_lower or 'like this' in question_lower or 'compare' in question_lower:
        return responses['similar']
    elif 'next' in question_lower or 'should i' in question_lower or 'action' in question_lower:
        return responses['next']
    elif 'policy' in question_lower or 'rule' in question_lower or 'regulation' in question_lower:
        return responses['policy']
    elif 'approval' in question_lower or 'review' in question_lower:
        return responses['approval']
    else:
        return 'I understand your question. Based on the exception details and historical patterns, I\'ve analyzed this case. Would you like me to focus on: (1) Root cause analysis, (2) Similar cases, (3) Recommended actions, (4) Policy requirements, or (5) Approval status?'
