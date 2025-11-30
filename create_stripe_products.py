# setup_stripe_products.py
import stripe
import os
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")  # Must be sk_test_ or sk_live_
STRIPE_SECRET_KEY=os.getenv("STRIPE_SECRET_KEY")
# -----------------------------
# Create Product
# -----------------------------
product = stripe.Product.create(
    name="Pro Plan",
    description="Access to all premium features"
)

# -----------------------------
# Monthly Plan - $39/month
# -----------------------------
monthly_price = stripe.Price.create(
    product=product.id,
    unit_amount=3900,  # 39.00 USD
    currency="usd",
    recurring={"interval": "month"}
)

# -----------------------------
# Yearly Plan - Special Discount
# Original: $468/year
# 20% Discount = $468/year
# -----------------------------
yearly_price = stripe.Price.create(
    product=product.id,
    unit_amount=46800,  # 468.00 USD after discount
    currency="usd",
    recurring={"interval": "year"}
)

print(f"Product ID: {product.id}")
print(f"Monthly Price ID: {monthly_price.id}")
print(f"Yearly Price ID (discounted): {yearly_price.id}")
