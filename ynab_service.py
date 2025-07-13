from flask import Flask, jsonify
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

@app.route('/health')
def health():
    """Health check endpoint"""
    cache_age = time.time() - cache['timestamp'] if cache['data'] else 0
    monthly_cache_age = time.time() - monthly_cache['timestamp'] if monthly_cache['data'] else 0
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
        }
    })

@app.route('/cache/clear')
def clear_cache():
    """Clear the cache"""
    cache['data'] = None
    cache['timestamp'] = 0
    monthly_cache['data'] = None
    monthly_cache['timestamp'] = 0
    return jsonify({'message': 'Cache cleared', 'timestamp': datetime.now().isoformat()})

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 