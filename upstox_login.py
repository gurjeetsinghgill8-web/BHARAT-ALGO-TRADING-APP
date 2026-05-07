import requests
import urllib.parse
import os
import db

def main():
    print("="*60)
    print(" BHARAT ALGOVERSE - UPSTOX TOKEN GENERATOR (v3.0) ")
    print("="*60)
    
    # 1. Ask for API details (or load from db if available)
    api_key = db.get_param('upstox_api_key', '')
    api_secret = db.get_param('upstox_api_secret', '')
    redirect_uri = db.get_param('upstox_redirect_uri', 'https://127.0.0.1')
    
    print("\n[Step 1] Enter your Upstox API details (Press Enter to use saved values):")
    
    in_key = input(f"API Key [{api_key}]: ").strip()
    if in_key: api_key = in_key
        
    in_secret = input(f"API Secret [{api_secret}]: ").strip()
    if in_secret: api_secret = in_secret
        
    in_redirect = input(f"Redirect URI [{redirect_uri}]: ").strip()
    if in_redirect: redirect_uri = in_redirect
        
    if not api_key or not api_secret:
        print("\n❌ Error: API Key and API Secret are required!")
        return

    # Save them back for future use
    db.set_param('upstox_api_key', api_key)
    db.set_param('upstox_api_secret', api_secret)
    db.set_param('upstox_redirect_uri', redirect_uri)

    # 2. Generate Login URL
    params = {
        'response_type': 'code',
        'client_id': api_key,
        'redirect_uri': redirect_uri
    }
    auth_url = "https://api.upstox.com/v2/login/authorization/dialog?" + urllib.parse.urlencode(params)
    
    print("\n" + "="*60)
    print(" [Step 2] Please open this exact link in your web browser:")
    print("="*60)
    print(auth_url)
    print("="*60)
    print("\n👉 Log in with your Upstox Phone Number and 6-digit PIN/OTP.")
    print("👉 After successful login, the browser will redirect you to a blank page or error page.")
    print("👉 Look at the URL in the address bar. It will look like:")
    print(f"   {redirect_uri}?code=XXXXXX")
    print("👉 Copy the exact code (XXXXXX) and paste it below.")
    
    code = input("\n[Step 3] Enter the copied code here: ").strip()
    if not code:
        print("\n❌ Error: Code cannot be empty!")
        return
        
    # 3. Exchange Code for Token
    print("\n⏳ Fetching new Access Token from Upstox...")
    url = "https://api.upstox.com/v2/login/authorization/token"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'code': code,
        'client_id': api_key,
        'client_secret': api_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            token = response.json().get('access_token')
            if token:
                db.set_param('upstox_access_token', token)
                
                # Also try to update secrets.txt if it exists
                if os.path.exists('secrets.txt'):
                    with open('secrets.txt', 'a') as f:
                        f.write(f"\nUPSTOX_ACCESS_TOKEN={token}\n")
                        
                print("\n" + "✅"*10)
                print(" SUCCESS! Your new Upstox Token is saved and active!")
                print(" You can now close this and restart the Nifty Algo!")
                print("✅"*10)
            else:
                print("\n❌ Error: Received success response but no access_token found inside.")
        else:
            print(f"\n❌ FAILED! Upstox returned error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"\n❌ Exception occurred: {str(e)}")

if __name__ == "__main__":
    main()
