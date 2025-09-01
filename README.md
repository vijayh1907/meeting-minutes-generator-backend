# To install required packages
# pip install -r requirements.txt

# To start the server
# uvicorn landing_page:app --reload

# If want to use specific port and ip, use below command and not any change in code
uvicorn landing_page:app --host 0.0.0.0 --port 9000 --reload

# To check endpoint locally
http://127.0.0.1:8000/

# Curl command to check 
curl http://127.0.0.1:8000/