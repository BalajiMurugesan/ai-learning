import streamlit as st
import sqlite3
import pandas as pd
import os

DB_NAME = "expenses.db"
PAGE_SIZE = 10  # Limited to 10 records per page

st.set_page_config(page_title="Saved Expenses", page_icon="📊", layout="wide")
st.title("📊 My Personal Expenses")

def get_total_records():
    if not os.path.exists(DB_NAME):
        return 0
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM expenses")
        return cursor.fetchone()[0]

def get_paginated_expenses(limit: int, offset: int):
    if not os.path.exists(DB_NAME):
        return pd.DataFrame()
    with sqlite3.connect(DB_NAME) as conn:
        query = """
            SELECT id, transaction_date, amount, currency, transaction_type, narrative, raw_input
            FROM expenses
            ORDER BY id
            LIMIT ? OFFSET ?
        """
        return pd.read_sql_query(query, conn, params=(limit, offset))

total_count = get_total_records()

if total_count == 0:
    st.info("No expenses found in the database. Use the Home page to add your first expense!")
else:
    st.write(f"Total Recorded Expenses: **{total_count}**")

    # Initialize session state for current page
    if "page_num" not in st.session_state:
        st.session_state.page_num = 1

    # Compute total number of pages using //. Any remainder records
    # get their own page.
    total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)

    # Ensure page number stays within valid range
    if st.session_state.page_num > total_pages:
        st.session_state.page_num = total_pages

    # Pagination Controls using Left & Right Arrow Buttons
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev: # Target the left column for rendering
        # Render the 'Previous' button; disable it if already on page 1 or lower
        if st.button("◀ Previous", disabled=st.session_state.page_num <= 1, use_container_width=True):
            st.session_state.page_num -= 1 # Decrement the current page tracker
            st.rerun() # Refresh the app immediately to load the previous page's content

    with col_info: # Target the center/middle column for the page indicator
        # Render custom HTML to display current page and total pages neatly
        st.markdown(
            f"<div style='text-align: center; padding-top: 8px;'>Page <b>{st.session_state.page_num}</b> of <b>{total_pages}</b></div>",
            unsafe_allow_html=True # Allow raw HTML/CSS parsing for text alignment and padding
        )

    with col_next: # Target the right column for rendering
        # Render the 'Next' button; disable it if already on the final page or higher
        if st.button("Next ▶", disabled=st.session_state.page_num >= total_pages, use_container_width=True):
            st.session_state.page_num += 1 # Increment the current page tracker
            st.rerun() # Refresh the app immediately to load the next page's content

    # Calculate SQL OFFSET
    offset = (st.session_state.page_num - 1) * PAGE_SIZE
    df = get_paginated_expenses(PAGE_SIZE, offset)

    # Display dataframe
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "id": "ID",
            "transaction_date": "Date",
            "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
            "currency": "Currency",
            "transaction_type": "Category",
            "narrative": "Narrative",
            "raw_input": "Original Input"
        },
        hide_index=True
    )