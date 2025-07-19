from flask import Flask, jsonify, request
import pandas as pd
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from ynab_sdk import YNAB
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Simple in-memory cache
cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 900  # 15 minutes in seconds
}

# Cache for monthly goals data
monthly_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 900  # 15 minutes in seconds
}

# Cache for savings rate data
savings_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 900  # 15 minutes in seconds
}

# Cache for net worth data
net_worth_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 900  # 15 minutes in seconds
}

def get_ynab_spending_data():
    """Get top 5 spending categories from last 30 days"""
    
    # Check cache first
    current_time = time.time()
    if cache['data'] and (current_time - cache['timestamp']) < cache['ttl']:
        return cache['data'], None
    
    try:
        # Get API token from environment
        api_token = os.getenv('YNAB_API_TOKEN')
        budget_id = os.getenv('YNAB_BUDGET_ID')
        
        if not api_token:
            return None, "API token not found"
            
        # Initialize YNAB client
        ynab = YNAB(api_token)
        
        # Get budget
        if budget_id:
            budget_response = ynab.budgets.get_budget(budget_id)
            budget = budget_response.data.budget
        else:
            budgets_response = ynab.budgets.get_budgets()
            if not budgets_response.data.budgets:
                return None, "No budgets found"
            budget = budgets_response.data.budgets[0]
            budget_id = budget.id
        
        # Get transactions
        transactions_response = ynab.transactions.get_transactions(budget_id)
        
        # Get categories
        categories_response = ynab.categories.get_categories(budget_id)
        
        # Process transactions
        tx_data = []
        for tx in transactions_response.data.transactions:
            tx_data.append({
                'date': tx.date,
                'amount': tx.amount / 1000,  # Convert from milliunits
                'category_id': tx.category_id,
                'category_name': tx.category_name,
                'payee_name': tx.payee_name
            })
        
        df = pd.DataFrame(tx_data)
        
        if df.empty:
            return None, "No transactions found"
        
        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Filter to last 30 days and expenses only
        thirty_days_ago = datetime.now() - timedelta(days=30)
        df = df[df['date'] >= thirty_days_ago]
        df = df[df['amount'] < 0]  # Only expenses
        df = df[df['category_name'] != 'Uncategorized']  # Remove uncategorized
        df['amount'] = df['amount'].abs()  # Make amounts positive
        
        # Add category groups
        category_groups = {}
        for group in categories_response.data.category_groups:
            for category in group.categories:
                category_groups[category.id] = group.name
        
        df['category_group'] = df['category_id'].map(category_groups)
        
        # Calculate spending by category group
        category_spending = df.groupby('category_group')['amount'].sum().reset_index()
        category_spending = category_spending.sort_values('amount', ascending=False)
        
        # Filter out Internal Master Category after grouping
        category_spending = category_spending[category_spending['category_group'] != 'Internal Master Category']
        
        # Get top 5
        top_5 = category_spending.head(5).copy()
        
        # Calculate percentages
        total_spending = df['amount'].sum()
        top_5['percentage'] = (top_5['amount'] / total_spending * 100).round(1)
        
        # Format for display
        result = []
        for _, row in top_5.iterrows():
            result.append({
                'category_group': row['category_group'],
                'amount': row['amount'],
                'amount_formatted': f"{row['amount']:,.0f}",  # US format with commas
                'percentage': row['percentage']
            })
        
        # Cache the result
        cache['data'] = result
        cache['timestamp'] = current_time
        
        return result, None
        
    except Exception as e:
        return None, str(e)

def get_monthly_goals_data():
    """Get current month spending vs category goals"""
    
    # Check cache first
    current_time = time.time()
    if monthly_cache['data'] and (current_time - monthly_cache['timestamp']) < monthly_cache['ttl']:
        return monthly_cache['data'], None
    
    try:
        # Get API token from environment
        api_token = os.getenv('YNAB_API_TOKEN')
        budget_id = os.getenv('YNAB_BUDGET_ID')
        
        if not api_token:
            return None, "API token not found"
            
        # Initialize YNAB client
        ynab = YNAB(api_token)
        
        # Get budget
        if budget_id:
            budget_response = ynab.budgets.get_budget(budget_id)
            budget = budget_response.data.budget
        else:
            budgets_response = ynab.budgets.get_budgets()
            if not budgets_response.data.budgets:
                return None, "No budgets found"
            budget = budgets_response.data.budgets[0]
            budget_id = budget.id
        
        # Get transactions for current month
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        transactions_response = ynab.transactions.get_transactions(budget_id)
        
        # Get categories with goals
        categories_response = ynab.categories.get_categories(budget_id)
        
        # Process transactions for current month
        tx_data = []
        for tx in transactions_response.data.transactions:
            tx_date = pd.to_datetime(tx.date)
            if tx_date >= start_of_month and tx.amount < 0:  # Current month expenses only
                tx_data.append({
                    'date': tx.date,
                    'amount': abs(tx.amount / 1000),  # Convert from milliunits and make positive
                    'category_id': tx.category_id,
                    'category_name': tx.category_name
                })
        
        if not tx_data:
            return [], None
        
        df = pd.DataFrame(tx_data)
        df = df[df['category_name'] != 'Uncategorized']  # Remove uncategorized
        
        # Add category assigned amounts to dataframe using whitelist
        
        # Whitelist of specific categories to include (in desired order)
        # Read from environment variable, fallback to default list
        categories_env = os.getenv('YNAB_MONTHLY_CATEGORIES')
        if categories_env:
            # Split by comma and strip whitespace
            whitelist_categories = [cat.strip() for cat in categories_env.split(',')]
        else:
            # Throw an error
            raise ValueError("YNAB_MONTHLY_CATEGORIES environment variable is not set")

        
        # Build assigned/budgeted amounts and category lookup for whitelisted categories
        category_assigned = {}
        category_lookup = {}  # name -> category object
        for group in categories_response.data.category_groups:
            for category in group.categories:
                if category.name in whitelist_categories:
                    assigned_amount = category.budgeted / 1000 if category.budgeted else 0
                    category_assigned[category.id] = assigned_amount
                    category_lookup[category.name] = category
        
        # Calculate spending by individual category
        category_spending = df.groupby(['category_id', 'category_name'])['amount'].sum().reset_index()
        
        # Create a lookup for spending amounts
        spending_lookup = {}
        for _, row in category_spending.iterrows():
            spending_lookup[row['category_id']] = row['amount']
        
        # Get all whitelisted categories in the specified order
        result = []
        for category_name in whitelist_categories:
            if category_name in category_lookup:
                category = category_lookup[category_name]
                category_id = category.id
                spent = spending_lookup.get(category_id, 0)  # 0 if no spending
                assigned_amount = category_assigned.get(category_id, 0)
                
                # Handle negative assigned amounts (transfers out of category)
                # If assigned is negative and available is 0, then no overspending occurred
                available_amount = category.balance / 1000 if category.balance else 0
                
                if assigned_amount < 0 and available_amount == 0:
                    # Money was transferred out and category is at zero - no overspending
                    difference = 0
                else:
                    # Normal calculation
                    difference = assigned_amount - spent
                
                result.append({
                    'category_name': category_name,
                    'spent': spent,
                    'spent_formatted': f"{spent:,.0f}",
                    'assigned': assigned_amount,
                    'assigned_formatted': f"{assigned_amount:,.0f}",
                    'available': available_amount,
                    'available_formatted': f"{available_amount:,.0f}",
                    'difference': difference,
                    'difference_formatted': f"{difference:,.2f}"
                })
        
        # Cache the result
        monthly_cache['data'] = result
        monthly_cache['timestamp'] = current_time
        
        return result, None
        
    except Exception as e:
        return None, str(e)

def get_savings_rate_data():
    """Get savings rate based on account balance changes and monthly income"""
    
    # Check cache first
    current_time = time.time()
    if savings_cache['data'] and (current_time - savings_cache['timestamp']) < savings_cache['ttl']:
        return savings_cache['data'], None
    
    try:
        # Get API token from environment
        api_token = os.getenv('YNAB_API_TOKEN')
        budget_id = os.getenv('YNAB_BUDGET_ID')
        monthly_income = os.getenv('YNAB_MONTHLY_INCOME')
        savings_accounts_env = os.getenv('YNAB_SAVINGS_ACCOUNTS')
        
        if not api_token:
            return None, "API token not found"
        
        if not monthly_income:
            return None, "Monthly income not set in environment variables"
            
        if not savings_accounts_env:
            return None, "Savings accounts not specified in environment variables"
            
        try:
            monthly_income = float(monthly_income)
        except ValueError:
            return None, "Monthly income must be a valid number"
        
        # Parse savings accounts list
        savings_accounts = [acc.strip() for acc in savings_accounts_env.split(',')]
            
        # Initialize YNAB client
        ynab = YNAB(api_token)
        
        # Get budget
        if budget_id:
            budget_response = ynab.budgets.get_budget(budget_id)
            budget = budget_response.data.budget
        else:
            budgets_response = ynab.budgets.get_budgets()
            if not budgets_response.data.budgets:
                return None, "No budgets found"
            budget = budgets_response.data.budgets[0]
            budget_id = budget.id
        
        # Get accounts
        accounts_response = ynab.accounts.get_accounts(budget_id)
        
        # Find savings accounts and get current balances
        savings_account_data = []
        total_current_balance = 0
        
        for account in accounts_response.data.accounts:
            if account.name in savings_accounts and not account.closed:
                current_balance = account.balance / 1000  # Convert from milliunits
                total_current_balance += current_balance
                
                savings_account_data.append({
                    'name': account.name,
                    'id': account.id,
                    'current_balance': current_balance,
                    'current_balance_formatted': f"{current_balance:,.2f}"
                })
        
        if not savings_account_data:
            return None, f"No open savings accounts found matching: {', '.join(savings_accounts)}"
        
        # Calculate monthly savings (simplified approach using transactions)
        # Get transactions for current month to savings accounts
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        transactions_response = ynab.transactions.get_transactions(budget_id)
        
        monthly_savings = 0
        savings_account_ids = [acc['id'] for acc in savings_account_data]
        
        for tx in transactions_response.data.transactions:
            tx_date = pd.to_datetime(tx.date)
            if (tx_date >= start_of_month and 
                tx.account_id in savings_account_ids and 
                tx.amount > 0):  # Positive amounts are money going into the account
                monthly_savings += tx.amount / 1000  # Convert from milliunits
        
        # Calculate savings rate
        savings_rate = (monthly_savings / monthly_income * 100) if monthly_income > 0 else 0
        
        # Prepare result
        result = {
            'monthly_income': monthly_income,
            'monthly_income_formatted': f"{monthly_income:,.2f}",
            'monthly_savings': monthly_savings,
            'monthly_savings_formatted': f"{monthly_savings:,.2f}",
            'savings_rate': round(savings_rate, 1),
            'total_savings_balance': total_current_balance,
            'total_savings_balance_formatted': f"{total_current_balance:,.2f}",
            'accounts': savings_account_data,
            'month': now.strftime('%B %Y')
        }
        
        # Cache the result
        savings_cache['data'] = result
        savings_cache['timestamp'] = current_time
        
        return result, None
        
    except Exception as e:
        return None, str(e)

def get_net_worth_data():
    """Calculate net worth from all account balances"""
    
    # Check cache first
    current_time = time.time()
    if net_worth_cache['data'] and (current_time - net_worth_cache['timestamp']) < net_worth_cache['ttl']:
        return net_worth_cache['data'], None
    
    try:
        # Get API token from environment
        api_token = os.getenv('YNAB_API_TOKEN')
        budget_id = os.getenv('YNAB_BUDGET_ID')
        
        if not api_token:
            return None, "API token not found"
            
        # Initialize YNAB client
        ynab = YNAB(api_token)
        
        # Get budget
        if budget_id:
            budget_response = ynab.budgets.get_budget(budget_id)
            budget = budget_response.data.budget
        else:
            budgets_response = ynab.budgets.get_budgets()
            if not budgets_response.data.budgets:
                return None, "No budgets found"
            budget = budgets_response.data.budgets[0]
            budget_id = budget.id
        
        # Get all accounts
        accounts_response = ynab.accounts.get_accounts(budget_id)
        
        # Initialize categories for net worth calculation
        assets = {
            'checking': [],
            'savings': [],
            'investment': [],
            'retirement': [],
            'property': [],
            'other_assets': []
        }
        
        liabilities = {
            'credit_cards': [],
            'loans': [],
            'other_debt': []
        }
        
        total_assets = 0
        total_liabilities = 0
        
        # Process each account
        for account in accounts_response.data.accounts:
            if account.closed:
                continue  # Skip closed accounts
                
            balance = account.balance / 1000  # Convert from milliunits
            account_data = {
                'name': account.name,
                'balance': balance,
                'balance_formatted': f"{balance:,.2f}",
                'on_budget': account.on_budget
            }
            
            # Categorize accounts by type
            if account.type == 'checking':
                assets['checking'].append(account_data)
                if balance > 0:
                    total_assets += balance
                else:
                    total_liabilities += abs(balance)
            
            elif account.type == 'savings':
                assets['savings'].append(account_data)
                if balance > 0:
                    total_assets += balance
                else:
                    total_liabilities += abs(balance)
            
            elif account.type == 'creditCard':
                liabilities['credit_cards'].append(account_data)
                total_liabilities += abs(balance)  # Credit card balances are negative
            
            elif account.type in ['autoLoan', 'studentLoan', 'personalLoan', 'mortgageLoan']:
                liabilities['loans'].append(account_data)
                total_liabilities += abs(balance)  # Loan balances are negative
            
            elif account.type == 'otherAsset':
                # Determine if it's investment/retirement based on name
                name_lower = account.name.lower()
                if any(term in name_lower for term in ['401k', '403b', 'ira', 'roth', 'pension']):
                    assets['retirement'].append(account_data)
                elif any(term in name_lower for term in ['investment', 'brokerage', 'stock', 'etf', 'mutual']):
                    assets['investment'].append(account_data)
                elif any(term in name_lower for term in ['house', 'home', 'property', 'real estate', 'car', 'vehicle']):
                    assets['property'].append(account_data)
                else:
                    assets['other_assets'].append(account_data)
                
                if balance > 0:
                    total_assets += balance
                else:
                    total_liabilities += abs(balance)
            
            elif account.type == 'otherDebt':
                liabilities['other_debt'].append(account_data)
                total_liabilities += abs(balance)
            
            else:
                # Catch-all for unknown account types
                assets['other_assets'].append(account_data)
                if balance > 0:
                    total_assets += balance
                else:
                    total_liabilities += abs(balance)
        
        # Calculate net worth
        net_worth = total_assets - total_liabilities
        
        # Calculate totals for each category
        asset_totals = {}
        for category, accounts in assets.items():
            total = sum(acc['balance'] for acc in accounts if acc['balance'] > 0)
            asset_totals[category] = {
                'total': total,
                'total_formatted': f"{total:,.2f}",
                'accounts': accounts,
                'count': len(accounts)
            }
        
        liability_totals = {}
        for category, accounts in liabilities.items():
            total = sum(abs(acc['balance']) for acc in accounts)
            liability_totals[category] = {
                'total': total,
                'total_formatted': f"{total:,.2f}",
                'accounts': accounts,
                'count': len(accounts)
            }
        
        # Prepare result
        result = {
            'net_worth': net_worth,
            'net_worth_formatted': f"{net_worth:,.2f}",
            'total_assets': total_assets,
            'total_assets_formatted': f"{total_assets:,.2f}",
            'total_liabilities': total_liabilities,
            'total_liabilities_formatted': f"{total_liabilities:,.2f}",
            'assets': asset_totals,
            'liabilities': liability_totals,
            'updated': datetime.now().strftime('%B %d, %Y at %I:%M %p')
        }
        
        # Cache the result
        net_worth_cache['data'] = result
        net_worth_cache['timestamp'] = current_time
        
        return result, None
        
    except Exception as e:
        return None, str(e)

@app.route('/api/spending')
def api_spending():
    """JSON API endpoint"""
    data, error = get_ynab_spending_data()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/glance')
def glance_data():
    """Simplified endpoint optimized for Glance custom-api widget"""
    data, error = get_ynab_spending_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Format data for Glance template
    response = {
        'categories': data,
        'updated': datetime.now().strftime('%I:%M %p'),
        'total_categories': len(data)
    }
    
    return jsonify(response)

@app.route('/spending-trends')
def spending_trends():
    """30-day spending trends endpoint - top 5 category groups"""
    data, error = get_ynab_spending_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Format data for Glance template
    response = {
        'categories': data,
        'updated': datetime.now().strftime('%I:%M %p'),
        'total_categories': len(data)
    }
    
    return jsonify(response)

@app.route('/api/monthly-goals')
def api_monthly_goals():
    """JSON API endpoint for monthly spending vs goals"""
    data, error = get_monthly_goals_data()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/monthly-goals')
def monthly_goals_glance():
    """Glance endpoint for monthly spending vs goals"""
    data, error = get_monthly_goals_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Format data for Glance template
    response = {
        'categories': data,
        'updated': datetime.now().strftime('%I:%M %p'),
        'total_categories': len(data)
    }
    
    return jsonify(response)

@app.route('/api/savings-rate')
def api_savings_rate():
    """JSON API endpoint for savings rate data"""
    data, error = get_savings_rate_data()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/savings-rate')
def savings_rate_glance():
    """Glance endpoint for savings rate widget"""
    data, error = get_savings_rate_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Format data for Glance template
    response = {
        'savings_data': data,
        'updated': datetime.now().strftime('%I:%M %p')
    }
    
    return jsonify(response)

@app.route('/api/net-worth')
def api_net_worth():
    """JSON API endpoint for net worth data"""
    data, error = get_net_worth_data()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/net-worth')
def net_worth_glance():
    """Glance endpoint for net worth widget"""
    data, error = get_net_worth_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Format data for Glance template
    response = {
        'net_worth_data': data,
        'updated': datetime.now().strftime('%I:%M %p')
    }
    
    return jsonify(response)

@app.route('/health')
def health():
    """Health check endpoint"""
    cache_age = time.time() - cache['timestamp'] if cache['data'] else 0
    monthly_cache_age = time.time() - monthly_cache['timestamp'] if monthly_cache['data'] else 0
    savings_cache_age = time.time() - savings_cache['timestamp'] if savings_cache['data'] else 0
    net_worth_cache_age = time.time() - net_worth_cache['timestamp'] if net_worth_cache['data'] else 0
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'spending_cache': {
            'age_seconds': cache_age,
            'valid': cache_age < cache['ttl'] if cache['data'] else False
        },
        'monthly_goals_cache': {
            'age_seconds': monthly_cache_age,
            'valid': monthly_cache_age < monthly_cache['ttl'] if monthly_cache['data'] else False
        },
        'savings_cache': {
            'age_seconds': savings_cache_age,
            'valid': savings_cache_age < savings_cache['ttl'] if savings_cache['data'] else False
        },
        'net_worth_cache': {
            'age_seconds': net_worth_cache_age,
            'valid': net_worth_cache_age < net_worth_cache['ttl'] if net_worth_cache['data'] else False
        }
    })

@app.route('/cache/clear')
def clear_cache():
    """Clear all caches"""
    cache['data'] = None
    cache['timestamp'] = 0
    monthly_cache['data'] = None
    monthly_cache['timestamp'] = 0
    savings_cache['data'] = None
    savings_cache['timestamp'] = 0
    net_worth_cache['data'] = None
    net_worth_cache['timestamp'] = 0
    return jsonify({'message': 'All caches cleared', 'timestamp': datetime.now().isoformat()})

@app.route('/debug/category-groups')
def debug_category_groups():
    """Debug endpoint to show all category group names"""
    try:
        # Get API token from environment
        api_token = os.getenv('YNAB_API_TOKEN')
        budget_id = os.getenv('YNAB_BUDGET_ID')
        
        if not api_token:
            return jsonify({'error': 'API token not found'}), 500
            
        # Initialize YNAB client
        ynab = YNAB(api_token)
        
        # Get budget
        if budget_id:
            budget_response = ynab.budgets.get_budget(budget_id)
            budget = budget_response.data.budget
        else:
            budgets_response = ynab.budgets.get_budgets()
            if not budgets_response.data.budgets:
                return jsonify({'error': 'No budgets found'}), 500
            budget = budgets_response.data.budgets[0]
            budget_id = budget.id
        
        # Get categories
        categories_response = ynab.categories.get_categories(budget_id)
        
        # Show all category groups and their categories
        result = {}
        for group in categories_response.data.category_groups:
            group_categories = []
            for category in group.categories:
                group_categories.append({
                    'id': category.id,
                    'name': category.name,
                    'has_goal': category.goal_target is not None
                })
            result[group.name] = {
                'repr': repr(group.name),
                'categories': group_categories
            }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/monthly-goals-order')
def debug_monthly_goals_order():
    """Debug endpoint to show the exact order of monthly goals data"""
    # Clear cache to get fresh data
    monthly_cache['data'] = None
    monthly_cache['timestamp'] = 0
    
    data, error = get_monthly_goals_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Show the exact order with index numbers
    debug_result = []
    for i, item in enumerate(data):
        debug_result.append({
            'index': i,
            'category_name': item['category_name'],
            'difference': item['difference'],
            'difference_formatted': item['difference_formatted'],
            'assigned': item['assigned'],
            'spent': item['spent'],
            'available': item.get('available', 'N/A')
        })
    
    return jsonify({
        'total_items': len(debug_result),
        'items': debug_result
    })

@app.route('/debug/accounts')
def debug_accounts():
    """Debug endpoint to show all account names"""
    try:
        # Get API token from environment
        api_token = os.getenv('YNAB_API_TOKEN')
        budget_id = os.getenv('YNAB_BUDGET_ID')
        
        if not api_token:
            return jsonify({'error': 'API token not found'}), 500
            
        # Initialize YNAB client
        ynab = YNAB(api_token)
        
        # Get budget
        if budget_id:
            budget_response = ynab.budgets.get_budget(budget_id)
            budget = budget_response.data.budget
        else:
            budgets_response = ynab.budgets.get_budgets()
            if not budgets_response.data.budgets:
                return jsonify({'error': 'No budgets found'}), 500
            budget = budgets_response.data.budgets[0]
            budget_id = budget.id
        
        # Get accounts
        accounts_response = ynab.accounts.get_accounts(budget_id)
        
        # Show all accounts with their details
        result = []
        for account in accounts_response.data.accounts:
            result.append({
                'id': account.id,
                'name': account.name,
                'type': account.type,
                'balance': account.balance / 1000,  # Convert from milliunits
                'balance_formatted': f"{account.balance / 1000:,.2f}",
                'closed': account.closed,
                'on_budget': account.on_budget
            })
        
        return jsonify({
            'total_accounts': len(result),
            'accounts': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 