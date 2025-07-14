import streamlit as st
import mysql.connector
from openai import OpenAI # Ensure you have the openai library installed

# --- Configuration ---
# You can set a default API key or leave it empty for user input
# OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# --- Database Connection Function ---
def get_db_connection(db_host, db_user, db_password, db_name):
    """Establishes and returns a database connection."""
    try:
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error connecting to database: {err}")
        return None

# --- Get Database Schema (for LLM context) ---
def get_table_schema(connection):
    """Fetches schema information for all tables in the connected database."""
    if not connection:
        return {}

    cursor = connection.cursor()
    schema_info = {}

    try:
        # Get all table names
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]

        for table_name in tables:
            # Get column information for each table
            cursor.execute(f"DESCRIBE {table_name}")
            columns = []
            for col in cursor.fetchall():
                col_name = col[0]
                col_type = col[1]
                columns.append(f"{col_name} {col_type}")
            schema_info[table_name] = ", ".join(columns)
    except mysql.connector.Error as err:
        st.error(f"Error fetching database schema: {err}")
    finally:
        cursor.close()
    return schema_info

# --- Generate SQL using OpenAI ---
def generate_sql_query(natural_language_question, db_schema, openai_api_key):
    """
    Generates an SQL query from a natural language question using OpenAI.
    """
    if not openai_api_key:
        st.warning("Please enter your OpenAI API Key in the sidebar.")
        return None

    try:
        client = OpenAI(api_key=openai_api_key)

        # Construct the prompt for the LLM
        prompt = f"""
        You are an expert in SQL. Given the database schema below and a natural language question,
        generate a valid SQL query.
        Do not include any explanations or extra text, just the SQL query.

        Database Schema:
        {db_schema}

        Natural Language Question: "{natural_language_question}"

        SQL Query:
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # You can use other models like "gpt-4" if available
            messages=[
                {"role": "system", "content": "You are an expert SQL query generator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.1,
        )
        sql_query = response.choices[0].message.content.strip()
        return sql_query
    except Exception as e:
        st.error(f"Error generating SQL query with OpenAI: {e}")
        return None

# --- Streamlit UI ---
st.set_page_config(page_title="Dynamic SQL Chatbot", layout="wide")

st.title("🤖 Dynamic SQL Chatbot")
st.subheader("Ask Your SQL Question")

# --- Sidebar for Database Connection ---
st.sidebar.header("Connect to Your Database")

db_type = st.sidebar.selectbox("Database Type", ["MySQL"]) # Extendable for other DB types
db_user = st.sidebar.text_input("DB User", value="root")
db_password = st.sidebar.text_input("DB Password", type="password")
db_host = st.sidebar.text_input("DB Host", value="localhost")
db_name = st.sidebar.text_input("DB Name", value="classicmodels") # Example default
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

connect_button = st.sidebar.button("Connect")

# Initialize connection and schema in session state
if 'db_connection' not in st.session_state:
    st.session_state.db_connection = None
if 'db_schema' not in st.session_state:
    st.session_state.db_schema = {}
if 'connected' not in st.session_state:
    st.session_state.connected = False

if connect_button:
    with st.spinner("Connecting to database and fetching schema..."):
        conn = get_db_connection(db_host, db_user, db_password, db_name)
        if conn:
            st.session_state.db_connection = conn
            st.session_state.db_schema = get_table_schema(conn)
            st.session_state.connected = True
            st.sidebar.success("Successfully connected to database!")
        else:
            st.session_state.connected = False
            st.sidebar.error("Failed to connect to database.")

if st.session_state.connected:
    st.sidebar.write(f"Connected to: **{db_name}** on **{db_host}**")
else:
    st.sidebar.warning("Please connect to a database to proceed.")

# --- Main Chatbot Area ---
natural_language_question = st.text_area(
    "Enter your question below:",
    height=150,
    placeholder="e.g., For each productLine, compute total profit across all orders, and rank lines by profitability."
)

run_query_button = st.button("Run Query")

if run_query_button:
    if not st.session_state.connected:
        st.error("Please connect to the database first in the sidebar.")
    elif not natural_language_question.strip():
        st.warning("Please enter a question.")
    elif not openai_api_key:
        st.warning("Please enter your OpenAI API Key in the sidebar.")
    else:
        with st.spinner("Generating SQL query..."):
            sql_query = generate_sql_query(
                natural_language_question,
                st.session_state.db_schema,
                openai_api_key
            )

            if sql_query:
                st.subheader("Generated SQL Query:")
                st.code(sql_query, language="sql")

                # Optional: Execute the query and display results
                # if st.button("Execute Generated Query"):
                #     if st.session_state.db_connection:
                #         try:
                #             cursor = st.session_state.db_connection.cursor()
                #             cursor.execute(sql_query)
                #             results = cursor.fetchall()
                #             column_names = [desc[0] for desc in cursor.description]
                #             st.subheader("Query Results:")
                #             st.dataframe(results, columns=column_names)
                #         except mysql.connector.Error as err:
                #             st.error(f"Error executing query: {err}")
                #         finally:
                #             cursor.close()
                #     else:
                #         st.error("Database connection lost. Please reconnect.")
            else:
                st.error("Could not generate SQL query. Please check your OpenAI API key and question.")

# --- Close DB Connection on App Exit (Best practice) ---
# This part is tricky with Streamlit's rerun nature.
# For a simple app, it's often handled by the process ending.
# For more robust handling, you might use a callback or a more complex session management.
# For now, we'll rely on the connection being closed when the script finishes.
# You could add a disconnect button or a more sophisticated cleanup if needed.
