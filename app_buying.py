import os
import sys

# Set instance to BUYING
os.environ['BOT_INSTANCE'] = 'BUYING'

# Run the streamlit app
# We use this trick to keep the same codebase but change the DB context
import streamlit.web.cli as stcli

if __name__ == "__main__":
    # Standard Streamlit port is 8501
    sys.argv = ["streamlit", "run", "app.py", "--server.port", "8501"]
    sys.exit(stcli.main())
