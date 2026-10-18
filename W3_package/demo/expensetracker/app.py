import streamlit as st

st.set_page_config(
    page_title="AI Expense Tracker",
    page_icon="💰",
    layout="wide"
)

# Define your pages with custom titles and icons
home_page = st.Page(
    page="pages/home.py", 
    title="Home", 
    icon="🏠", 
    default=True
)

expense_page = st.Page(
    page="pages/expenses.py", 
    title="Expense", 
    icon="📊"
)

# Setup navigation menu
pg = st.navigation([home_page, expense_page])

# Run the selected page
pg.run()