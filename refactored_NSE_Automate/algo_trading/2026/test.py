"This is a test file for the algo trading project."
import argparse
import sys

def get_code(api_key, redirect_url):
    """ """
    url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={redirect_url}&response_type=code"
    print(f"Open this Upstox URL and complete the authorization: {url}")
    print("After authorization, you will be redirected to the redirect URL with a code parameter.")
    print("Please copy the code parameter from the URL and paste it here.")
    print("Example: If the redirect URL is http://127.0.0.1:8080/callback?code=xXx0E00, then the code is xXx0E0")
    code = input("Enter the code: ")
    print(f"Received code: {code}")

    return code

# ------------------------------------------------------------------

def main():
    """ """
    parser = argparse.ArgumentParser(description="Algo Trading Test")
    parser.add_argument("api_key", type=str, help="API key for authentication")
    parser.add_argument("api_secret", type=str, help="API secret for authentication")
    parser.add_argument("redirect_url", type=str, help="Redirect URL for authentication")
    args = parser.parse_args(sys.argv[1:])

    print("API Key:", args.api_key)
    print("API Secret:", args.api_secret)
    print("Redirect URL:", args.redirect_url)

    code  = get_code(args.api_key, args.redirect_url)
    print("Authorization code received:", code)

# ------------------------------------------------------------------

if __name__ == "__main__":
    main()