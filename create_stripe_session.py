import stripe
import os
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")  # sk_test_...

# Your price IDs
MONTHLY_PRICE_ID = "price_1SWMauSBcaUtv6fpCztlUeM3"
YEARLY_PRICE_ID = "price_1SWMauSBcaUtv6fpDXIFPJ4T"

def create_checkout_session(price_id):
    session = stripe.checkout.Session.create(
        mode="subscription",
        success_url="http://localhost:8000/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://localhost:8000/cancel",
        line_items=[
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
    )

    return session.url


if __name__ == "__main__":
    # Choose plan here:
    print("Select Plan:")
    print("1. Monthly ($39)")
    print("2. Yearly ($374)")

    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        url = create_checkout_session(MONTHLY_PRICE_ID)
        print("\n👉 Monthly Checkout URL:")
    elif choice == "2":
        url = create_checkout_session(YEARLY_PRICE_ID)
        print("\n👉 Yearly Checkout URL:")
    else:
        print("Invalid choice.")
        exit()

    print(url)
    print("\nOpen the above link in your browser.")
