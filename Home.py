import streamlit as st

# Set the title of the Streamlit app
st.title("Request for Proposal (RFP)")

st.set_page_config(
  page_title = 'Home Page'
)

# Add some introductory text
st.write("""
Welcome to the Request for Proposal (RFP) page.

Please select the appropriate page for your RFP needs:
- **Hitachi Content Platform (HCP)**: Navigate to the "Hitachi Content Platform" page for HCP-related RFPs.
- **NetApp**: Navigate to the "NetApp" page for NetApp-related RFPs.
""")
