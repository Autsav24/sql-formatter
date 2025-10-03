import streamlit as st
from io import StringIO
from datetime import datetime

# ---------- Optional deps ----------
# Prefer sqlglot for robust, dialect-aware formatting.
# If it's not available, fall back to sqlparse (limited/no dialect support).
try:
    import sqlglot
    from sqlglot import parse_one
    HAVE_SQLGLOT = True
except Exception:
    HAVE_SQLGLOT = False

try:
    import sqlparse
    HAVE_SQLPARSE = True
except Exception:
    HAVE_SQLPARSE = False

st.set_page_config(page_title="SQL Formatter • Streamlit", page_icon="🧹", layout="wide")
st.title("🧹 SQL Formatter")
st.caption("Format, lint-lite, and prettify your SQL. Dialect-aware when **sqlglot** is available.")

# ---------------- Sidebar Controls ----------------
st.sidebar.header("Options")
example_sql = """
-- Paste your SQL here
select a.col1, b.col2, count(*) as total
from sales a
join customers b on a.customer_id = b.id
where a.order_date between '2024-01-01' and '2024-12-31' and b.country = 'IN'
group by 1,2
order by total desc;
""".strip()

with st.sidebar:
    dialect = st.selectbox(
        "Dialect (sqlglot only)",
        options=[
            "ansi","bigquery","clickhouse","databricks","duckdb","hive","mysql",
            "oracle","postgres","presto","redshift","snowflake","spark","sqlite","tsql"
        ],
        index=12  # default spark
    )

    keyword_case = st.selectbox("Keyword case", ["upper", "lower", "capitalize"], index=0)
    identifier_case = st.selectbox("Identifier case", ["preserve", "upper", "lower"], index=0)
    indent = st.number_input("Indent width", min_value=2, max_value=8, value=4, step=1)
    width = st.number_input("Max line width", min_value=40, max_value=200, value=120, step=5)
    leading_comma = st.toggle("Leading commas", value=False, help="If on, places commas at line starts where applicable.")
    normalize = st.toggle("Normalize (canonicalize)", value=False, help="Standardize some expressions (sqlglot).")
    remove_comments = st.toggle("Strip comments", value=False)
    compact = st.toggle("Compact/minify", value=False, help="Crush extra whitespace (overrides pretty settings).")
    single_line_safe = st.toggle("EOL '--' → block comments", value=False, help="Convert end-of-line double-dash comments to /* ... */ so queries survive single-line storage.")

    st.caption(
        "If **sqlglot** isn't installed, the app will fall back to **sqlparse** with limited options."
    )

# ---------------- I/O ----------------
col_in, col_out = st.columns([1, 1])

with col_in:
    st.subheader("Input SQL")
    uploaded = st.file_uploader("Upload .sql (optional)", type=["sql","txt"], accept_multiple_files=False)
    if uploaded is not None:
        raw_sql = uploaded.read().decode("utf-8", errors="ignore")
    else:
        raw_sql = st.text_area("Paste SQL", value=example_sql, height=260, placeholder="Paste your SQL…")

    apply_btn = st.button("Format SQL ✨", type="primary")

with col_out:
    st.subheader("Output")
    out_container = st.empty()

# ---------------- Helpers ----------------
def dash_to_block(sql: str) -> str:
    """Convert end-of-line `-- ...` comments to block comments.
    Example: SELECT 1 -- note  -> SELECT 1 /* note */
    Safer when queries are collapsed to a single line by storage layers.
    """
    import re
    # If you'd like the cross-platform tweak, change [^\n]* to [^\r\n]*
    return re.sub(r"--[^\n]*", lambda m: "/* " + m.group(0)[2:].strip() + " */", sql)

def format_with_sqlglot(sql: str) -> str:
    # Optional: make single-line safe by converting -- EOL comments first
    if single_line_safe:
        sql = dash_to_block(sql)
    # Remove comments if requested (sqlglot preserves comments otherwise)
    if remove_comments:
        import re
        sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
        sql = "\n".join([ln for ln in sql.splitlines() if not ln.strip().startswith("--")])

    if compact:
        try:
            return sqlglot.transpile(sql, read=dialect, pretty=False, identity=True)[0]
        except Exception:
            # best-effort minify: collapse whitespace
            return " ".join(sql.split())

    # Pretty formatting
    try:
        tree = parse_one(sql, read=dialect)
        formatted = tree.sql(
            pretty=True,
            keyword_case=keyword_case,
            identifier_case=None if identifier_case == "preserve" else identifier_case,
            indent=indent,
            max_text_width=width,
            leading_comma=leading_comma,
            normalize=normalize,
        )
        return formatted
    except Exception as e:
        # Try a simpler path
        try:
            return sqlglot.transpile(sql, read=dialect, pretty=True)[0]
        except Exception:
            raise e

def format_with_sqlparse(sql: str) -> str:
    if not HAVE_SQLPARSE:
        raise RuntimeError("Neither sqlglot nor sqlparse available.")

    if single_line_safe:
        sql = dash_to_block(sql)

    # sqlparse options
    kw_case = keyword_case.upper() if keyword_case != "capitalize" else "upper"

    if remove_comments:
        import re
        sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
        sql = "\n".join([ln for ln in sql.splitlines() if not ln.strip().startswith("--")])

    if compact:
        return sqlparse.format(sql, keyword_case=kw_case.lower(), strip_comments=remove_comments, reindent=False)

    return sqlparse.format(
        sql,
        keyword_case=kw_case.lower(),
        reindent=True,
        indent_width=indent,
        strip_comments=remove_comments,
    )

# ---------------- Action ----------------
if apply_btn:
    if not raw_sql or not raw_sql.strip():
        st.warning("Please paste or upload some SQL first.")
    else:
        try:
            if HAVE_SQLGLOT:
                pretty_sql = format_with_sqlglot(raw_sql)
            else:
                pretty_sql = format_with_sqlparse(raw_sql)

            out_container.code(pretty_sql, language="sql")

            # Download
            file_name = f"formatted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            st.download_button(
                label="Download .sql",
                data=pretty_sql.encode("utf-8"),
                file_name=file_name,
                mime="text/sql",
            )

            st.success("Formatted! 🎉")
        except Exception as e:
            st.error(f"Failed to format: {e}")

# ---------------- Footer ----------------
st.markdown("---")
st.caption(
    "Tip: For linting rules and auto-fixes, consider adding **sqlfluff** offline in CI; this app focuses on readable formatting."
)

# ----- Requirements (for reference) -----
# Create a requirements.txt with at least:
# streamlit>=1.34.0
# sqlglot>=25.0.0
# sqlparse>=0.5.0
